"""Recorrido del webhook al núcleo con transporte falso."""

import hashlib
import hmac
import json
from unittest.mock import patch

from django.test import TestCase, override_settings

from ambito.models import Comercio
from canales.models import MensajeEntrante, SalidaCanal, SesionCanal
from canales.worker import ciclo
from pedidos.models import Aceptacion, Pedido
from pedidos.servicios.tendero import operar


class TransporteFalso:
    def enviar_texto(self, sesion_id, chat_id, texto):
        return "id-enviado"


@override_settings(WAHA_WEBHOOK_SECRET="prueba", NUCLEO_ADAPTADOR="real")
class IntegracionRealTests(TestCase):
    def setUp(self):
        self.comercio = Comercio.objects.create(nombre="Tienda")
        SesionCanal.objects.create(
            instancia_id="waha", sesion_id="default", comercio=self.comercio
        )
        self.transporte = patch(
            "canales.worker.import_string", return_value=TransporteFalso
        )
        self.transporte.start()
        self.addCleanup(self.transporte.stop)

    def webhook(self, identidad, texto, **cambios):
        payload = {
            "id": identidad,
            "from": "123@c.us",
            "fromMe": False,
            "body": texto,
            **cambios,
        }
        cuerpo = json.dumps(
            {"event": "message", "session": "default", "payload": payload}
        ).encode()
        firma = hmac.new(b"prueba", cuerpo, hashlib.sha512).hexdigest()
        return self.client.post(
            "/api/webhooks/waha/",
            data=cuerpo,
            content_type="application/json",
            HTTP_X_WEBHOOK_HMAC=firma,
            HTTP_X_WEBHOOK_HMAC_ALGORITHM="sha512",
        )

    def cotizar(self):
        pedido = Pedido.objects.get()
        renglon = pedido.renglones.get()
        revisado = operar(
            self.comercio,
            pedido.id,
            "revisar_renglones",
            {
                "command_key": "rev",
                "expected_version": pedido.version,
                "renglones": [
                    {
                        "renglon_id": str(renglon.id),
                        "descripcion": "Leche",
                        "cantidad": "2",
                        "unidad": "pieza",
                        "precio_unitario_centavos": 1000,
                        "resolucion": "incluido",
                    }
                ],
            },
        )
        operar(
            self.comercio,
            pedido.id,
            "publicar_cotizacion",
            {"command_key": "pub", "expected_version": revisado.data["pedido"].version},
        )

    def test_recorrido_y_repeticion_sin_cobro(self):
        self.assertEqual(
            self.webhook("m1", "2 piezas de leche").json()["estado"], "recibido"
        )
        self.assertEqual(
            self.webhook("m1", "2 piezas de leche").json()["estado"], "duplicado"
        )
        ciclo()
        pedido = Pedido.objects.get()
        self.assertEqual(pedido.comercio_id, self.comercio.pk)
        self.assertEqual(pedido.renglones.get().texto_solicitado, "leche")
        self.cotizar()
        ciclo()
        resumen = SalidaCanal.objects.get(tipo="cotizacion_resumen")
        self.assertEqual(resumen.estado, "enviada")
        self.assertIn("$20.00", resumen.payload["texto"])
        token = resumen.payload["token_resumen"]
        self.webhook("m2", f"ACEPTAR {token}")
        ciclo()
        self.assertEqual(Aceptacion.objects.count(), 1)
        self.assertIn(
            "cobro aún no está habilitado",
            SalidaCanal.objects.filter(tipo="respuesta")
            .latest("creado_en")
            .payload["texto"],
        )
        self.assertEqual(Pedido.objects.count(), 1)

    def test_firma_mensaje_propio_y_grupo_no_crean_pedido(self):
        self.assertEqual(
            self.client.post(
                "/api/webhooks/waha/", data=b"{}", content_type="application/json"
            ).status_code,
            401,
        )
        self.assertEqual(
            self.webhook("m1", "hola", fromMe=True).json()["estado"], "ignorado"
        )
        self.assertEqual(
            self.webhook("m2", "hola", **{"from": "grupo@g.us"}).json()["estado"],
            "ignorado",
        )
        ciclo()
        self.assertFalse(Pedido.objects.exists())
        self.assertFalse(MensajeEntrante.objects.exists())

    def test_audio_no_guarda_media_ni_crea_pedido(self):
        self.webhook("a1", "secreto", hasMedia=True, mimetype="audio/ogg")
        ciclo()
        mensaje = MensajeEntrante.objects.get()
        self.assertEqual(
            (mensaje.tipo, mensaje.texto, mensaje.estado), ("audio", "", "ignorado")
        )
        self.assertIn(
            "solo recibimos texto", SalidaCanal.objects.get().payload["texto"]
        )
        self.assertFalse(Pedido.objects.exists())

    def test_rechaza_token_distinto(self):
        self.webhook("m1", "leche")
        ciclo()
        self.cotizar()
        ciclo()
        self.webhook("m2", "ACEPTAR otro")
        ciclo()
        self.assertFalse(Aceptacion.objects.exists())
        self.assertIn(
            "cambió",
            SalidaCanal.objects.filter(tipo="respuesta")
            .latest("creado_en")
            .payload["texto"],
        )

    def test_evento_obsoleto_no_envia_resumen_y_correccion_sustituye(self):
        self.webhook("m1", "leche")
        ciclo()
        self.cotizar()
        self.webhook("m2", "CORREGIR: pan")
        ciclo()
        pedido = Pedido.objects.get()
        self.assertEqual(pedido.renglones.get().texto_solicitado, "pan")
        self.assertFalse(SalidaCanal.objects.filter(tipo="cotizacion_resumen").exists())
        self.assertFalse(Aceptacion.objects.exists())

    def test_no_se_acepta_resumen_sin_confirmacion(self):
        self.webhook("m1", "leche")
        ciclo()
        self.cotizar()
        with patch.object(TransporteFalso, "enviar_texto", side_effect=TimeoutError):
            ciclo()
        resumen = SalidaCanal.objects.get(tipo="cotizacion_resumen")
        self.assertEqual(resumen.estado, "incierta")
        self.webhook("m2", f"ACEPTAR {resumen.payload['token_resumen']}")
        ciclo()
        self.assertFalse(Aceptacion.objects.exists())

    @override_settings(NUCLEO_ADAPTADOR="stub", NUCLEO_STUB_PERMITIDO=True)
    def test_stub_identifica_simulacion_y_conserva_pedido_entre_ciclos(self):
        import canales.worker as worker

        self.addCleanup(setattr, worker, "_nucleo_stub", None)
        worker._nucleo_stub = None
        self.webhook("m1", "leche")
        ciclo()
        self.assertTrue(
            SalidaCanal.objects.get().payload["texto"].startswith("[SIMULACIÓN]")
        )
        self.webhook("m2", "CORREGIR: pan")
        ciclo()
        self.assertIn(
            "corregido",
            SalidaCanal.objects.filter(tipo="respuesta")
            .latest("creado_en")
            .payload["texto"]
            .lower(),
        )
        self.assertEqual(len(worker._nucleo_stub.pedidos), 1)

    def test_cotizacion_preparada_invalidada_no_se_envia(self):
        from canales.avisos import procesar_avisos
        from pedidos.fabrica import obtener_lector, obtener_nucleo

        self.webhook("m1", "leche")
        ciclo()
        self.cotizar()
        procesar_avisos(obtener_nucleo(), obtener_lector())
        resumen = SalidaCanal.objects.get(tipo="cotizacion_resumen")
        self.assertEqual(resumen.estado, "preparada")
        self.webhook("m2", "CORREGIR: pan")
        ciclo()
        resumen.refresh_from_db()
        self.assertEqual(resumen.estado, "fallida")
        self.assertEqual(resumen.id_proveedor, "")
        self.assertFalse(Aceptacion.objects.exists())
