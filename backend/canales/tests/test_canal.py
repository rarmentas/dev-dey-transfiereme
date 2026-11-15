"""Casos de integridad del canal."""

import hashlib
import hmac
import json
from datetime import timedelta
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from ambito.models import Comercio
from canales.lector import LectorProcedenciaCanal
from canales.models import ConversacionCanal, MensajeEntrante, SalidaCanal, SesionCanal
from canales.parseo import parsear_renglones
from canales.salidas import enviar, recuperar_abandonadas
from canales.waha import ErrorEnvio
from pedidos.contratos.v1 import ContextoCanalV1


class ParseoTests(SimpleTestCase):
    def test_cantidad_decimal_separadores_y_vacio(self):
        filas = parsear_renglones("1,5 kg de arroz; leche\n2 piezas de pan", "m")
        self.assertEqual([r.texto_solicitado for r in filas], ["arroz", "leche", "pan"])
        self.assertEqual(str(filas[0].cantidad_solicitada), "1.5")
        self.assertIsNone(filas[1].cantidad_solicitada)
        self.assertEqual(parsear_renglones(" ; \n"), [])
        self.assertEqual(
            filas, parsear_renglones("1,5 kg de arroz; leche\n2 piezas de pan", "m")
        )


@override_settings(WAHA_WEBHOOK_SECRET="prueba")
class CanalTests(TestCase):
    def setUp(self):
        comercio = Comercio.objects.create(nombre="A")
        self.sesion = SesionCanal.objects.create(
            instancia_id="waha", sesion_id="s", comercio=comercio
        )
        self.chat = ConversacionCanal.objects.create(
            sesion=self.sesion, chat_id="a@c.us", cliente_externo_id="a@c.us"
        )
        self.ctx = ContextoCanalV1("waha", "s", str(self.chat.id), "a@c.us")

    def webhook(self, payload, firma=True):
        cuerpo = json.dumps(
            {"event": "message", "session": "s", "payload": payload}
        ).encode()
        digest = (
            hmac.new(b"prueba", cuerpo, hashlib.sha512).hexdigest() if firma else "x"
        )
        return self.client.post(
            "/api/webhooks/waha/",
            data=cuerpo,
            content_type="application/json",
            HTTP_X_WEBHOOK_HMAC=digest,
            HTTP_X_WEBHOOK_HMAC_ALGORITHM="sha512",
        )

    def test_duplicado_conflicto_y_secuencia(self):
        payload = {"id": "1", "from": "a@c.us", "fromMe": False, "body": "hola"}
        self.assertEqual(self.webhook(payload, False).status_code, 401)
        self.assertEqual(self.webhook(payload).json()["estado"], "recibido")
        self.assertEqual(self.webhook(payload).json()["estado"], "duplicado")
        self.assertEqual(
            self.webhook({**payload, "body": "otro"}).json()["estado"], "conflicto"
        )
        self.assertEqual(
            self.webhook({**payload, "id": "2"}).json()["estado"], "recibido"
        )
        self.assertEqual(
            list(
                MensajeEntrante.objects.order_by("secuencia").values_list(
                    "secuencia", flat=True
                )
            ),
            [1, 2],
        )

    def test_lector_aisla_conversacion_y_sesion(self):
        self.webhook({"id": "1", "from": "a@c.us", "fromMe": False, "body": "hola"})
        lector = LectorProcedenciaCanal()
        mensaje = MensajeEntrante.objects.get()
        self.assertEqual(
            lector.leer_mensaje(self.ctx, str(mensaje.id)).texto_normalizado, "hola"
        )
        ajeno = ContextoCanalV1("waha", "s", str(self.chat.id), "otro")
        self.assertIsNone(lector.resolver_comercio(ajeno))
        self.assertIsNone(lector.leer_mensaje(ajeno, str(mensaje.id)))
        self.sesion.estado = "inactiva"
        self.sesion.save()
        self.assertIsNone(lector.resolver_comercio(self.ctx))

    def test_envio_falla_cerrado_y_recupera_abandonados(self):
        salida = SalidaCanal.objects.create(
            conversacion=self.chat,
            causa="x",
            destinatario=self.chat.chat_id,
            tipo="respuesta",
            payload={"texto": "hola"},
        )

        class Fallo:
            def enviar_texto(self, *args):
                raise ErrorEnvio()

        enviar(salida.id, Fallo())
        salida.refresh_from_db()
        self.assertEqual(salida.estado, "incierta")
        with patch.object(Fallo, "enviar_texto") as llamada:
            enviar(salida.id, Fallo())
            llamada.assert_not_called()
        salida.estado = "enviando"
        salida.envio_iniciado_en = timezone.now() - timedelta(seconds=61)
        salida.save()
        self.assertEqual(recuperar_abandonadas(), 1)
        salida.refresh_from_db()
        self.assertEqual(salida.estado, "incierta")

    def test_respuesta_agente_muestra_escribiendo_antes_del_envio(self):
        salida = SalidaCanal.objects.create(
            conversacion=self.chat, causa="agente", destinatario=self.chat.chat_id,
            tipo="respuesta", payload={"texto": "Pedido recibido", "escribiendo": True},
        )
        eventos = []

        class Transporte:
            def iniciar_escritura(self, sesion, chat):
                eventos.append(("typing", sesion, chat))

            def detener_escritura(self, sesion, chat):
                eventos.append(("paused", sesion, chat))

            def enviar_texto(self, sesion, chat, texto):
                eventos.append(("texto", sesion, chat, texto))
                return "ack"

        with patch("canales.salidas.random.uniform", return_value=4.5), \
             patch("canales.salidas.time.sleep", side_effect=lambda segundos: eventos.append(("espera", segundos))):
            enviar(salida.pk, Transporte())
        self.assertEqual(eventos, [
            ("typing", "s", "a@c.us"), ("espera", 4.5),
            ("texto", "s", "a@c.us", "Pedido recibido"), ("paused", "s", "a@c.us"),
        ])
        salida.refresh_from_db()
        self.assertEqual(salida.estado, "enviada")

    def test_fallo_de_presencia_no_impide_respuesta(self):
        salida = SalidaCanal.objects.create(
            conversacion=self.chat, causa="agente-2", destinatario=self.chat.chat_id,
            tipo="respuesta", payload={"texto": "Hola", "escribiendo": True},
        )

        class Transporte:
            def iniciar_escritura(self, *_):
                raise OSError("sin presencia")

            def detener_escritura(self, *_):
                raise OSError("sin presencia")

            def enviar_texto(self, *_):
                return "ack"

        with patch("canales.salidas.time.sleep"):
            enviar(salida.pk, Transporte())
        salida.refresh_from_db()
        self.assertEqual(salida.estado, "enviada")

    def test_firma_algoritmo_y_cuerpo_grande_fallan_cerrado(self):
        cuerpo = b"{}"
        firma = hmac.new(b"prueba", cuerpo, hashlib.sha512).hexdigest()
        respuesta = self.client.post(
            "/api/webhooks/waha/",
            data=cuerpo,
            content_type="application/json",
            HTTP_X_WEBHOOK_HMAC=firma,
            HTTP_X_WEBHOOK_HMAC_ALGORITHM="sha256",
        )
        self.assertEqual(respuesta.status_code, 401)
        respuesta = self.client.post(
            "/api/webhooks/waha/",
            data=b"x" * 262145,
            content_type="application/json",
        )
        self.assertEqual(respuesta.status_code, 413)
        self.assertFalse(MensajeEntrante.objects.exists())

    def test_resumen_solo_disponible_con_ack(self):
        payload = {
            "cotizacion_id": "cotizacion",
            "token_resumen": "P1-R1",
            "cotizacion_revision": 1,
            "total_comercial_centavos": 100,
            "importe_efectivo_centavos": 100,
            "demo_mode": False,
            "politica_cobro_version": "normal-1",
            "texto": "resumen",
        }
        salida = SalidaCanal.objects.create(
            conversacion=self.chat,
            causa="evento",
            destinatario=self.chat.chat_id,
            tipo="cotizacion_resumen",
            payload=payload,
        )
        lector = LectorProcedenciaCanal()
        self.assertIsNone(lector.leer_resumen(self.ctx, "cotizacion"))
        salida.estado = "enviada"
        salida.id_proveedor = "ack"
        salida.envio_iniciado_en = timezone.now()
        salida.enviado_en = timezone.now()
        salida.save()
        resumen = lector.leer_resumen(self.ctx, "cotizacion")
        self.assertEqual(resumen.id_proveedor, "ack")
        self.assertEqual(resumen.token_resumen, "P1-R1")
        self.assertIsNone(lector.leer_resumen(self.ctx, "otra"))
