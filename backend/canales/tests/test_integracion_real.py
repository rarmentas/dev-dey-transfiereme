"""Recorrido del webhook al núcleo con transporte falso."""

import hashlib
import hmac
import json
from unittest.mock import patch

from django.test import TestCase, TransactionTestCase, override_settings

from ambito.models import Comercio
from canales.models import MensajeEntrante, SalidaCanal, SesionCanal
from canales.worker import ciclo
from pedidos.models import Aceptacion, Pedido
from pedidos.servicios.tendero import operar
from webhooks.tests.support.pey_webhook import SECRETO


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
            "exactamente",
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

    def test_b1_webhook_conserva_producto_y_cantidad(self):
        self.webhook("m1", "2 leche; 2 gr de sal; 12345 tortillas")
        ciclo()
        filas = list(Pedido.objects.get().renglones.order_by("posicion"))
        self.assertEqual(
            [f.texto_solicitado for f in filas], ["leche", "sal", "12345 tortillas"]
        )
        self.assertEqual(str(filas[0].cantidad_solicitada), "2.000")
        self.assertEqual(filas[1].unidad_solicitada, "gr")
        self.assertIsNone(filas[2].cantidad_solicitada)

    def test_b2_consentimiento_con_ack_pendiente_se_reintenta(self):
        from django.utils import timezone
        from canales.conversacion import contexto
        from canales.lector import LectorProcedenciaCanal
        from pedidos.fabrica import obtener_nucleo

        self.webhook("m1", "leche")
        ciclo()
        self.cotizar()
        from canales.avisos import procesar_avisos

        procesar_avisos(obtener_nucleo(), LectorProcedenciaCanal())
        resumen = SalidaCanal.objects.get(tipo="cotizacion_resumen")
        resumen.estado = "enviando"
        resumen.envio_iniciado_en = timezone.now()
        resumen.save()
        self.webhook("m2", f"ACEPTAR {resumen.payload['token_resumen']}")
        mensaje = MensajeEntrante.objects.get(id_mensaje_proveedor="m2")
        ctx = contexto(mensaje.conversacion)
        p = resumen.payload
        nucleo = obtener_nucleo()
        argumentos = dict(
            contrato_version="1.0",
            command_key=f"aceptacion:{mensaje.id}",
            pedido_id=p["pedido_id"],
            expected_version=p["pedido_version"],
            cotizacion_id=p["cotizacion_id"],
            cotizacion_revision=p["cotizacion_revision"],
            importe_efectivo_mostrado_centavos=p["importe_efectivo_centavos"],
            politica_cobro_version=p["politica_cobro_version"],
            mensaje_consentimiento_id=str(mensaje.id),
            token_resumen=p["token_resumen"],
        )
        self.assertTrue(nucleo.aceptar_cotizacion(ctx, **argumentos).error.retryable)
        ciclo()
        mensaje.refresh_from_db()
        self.assertEqual(mensaje.estado, "reintentable")
        self.assertFalse(Aceptacion.objects.exists())
        resumen.estado = "enviada"
        resumen.id_proveedor = "ack"
        resumen.enviado_en = timezone.now()
        resumen.save()
        MensajeEntrante.objects.filter(pk=mensaje.pk).update(
            proximo_intento_en=timezone.now()
        )
        ciclo()
        self.assertEqual(Aceptacion.objects.count(), 1)
        self.assertTrue(nucleo.aceptar_cotizacion(ctx, **argumentos).replayed)

    def test_i1_avisa_espera_y_agotamiento_con_clave_estable(self):
        from django.utils import timezone
        from canales.conversacion import procesar_mensaje
        from pedidos.contratos.v1 import CodigoError, ErrorV1, RespuestaV1
        from canales.lector import LectorProcedenciaCanal

        self.webhook("m1", "leche")
        mensaje = MensajeEntrante.objects.select_related("conversacion__sesion").get()
        nucleo = type("Nucleo", (), {"ES_SIMULACION": False})()
        nucleo.registrar_solicitud = __import__(
            "unittest.mock", fromlist=["Mock"]
        ).Mock(
            return_value=RespuestaV1(
                False,
                error=ErrorV1(
                    CodigoError.SERVICIO_NO_DISPONIBLE, "fallo", retryable=True
                ),
            )
        )
        for _ in range(6):
            mensaje.refresh_from_db()
            procesar_mensaje(mensaje, nucleo, LectorProcedenciaCanal(), timezone.now())
        mensaje.refresh_from_db()
        self.assertEqual((mensaje.estado, mensaje.intentos), ("fallido", 6))
        self.assertEqual(
            {
                c.kwargs["command_key"]
                for c in nucleo.registrar_solicitud.call_args_list
            },
            {f"registrar:{mensaje.id}"},
        )
        self.assertEqual(SalidaCanal.objects.filter(tipo="respuesta").count(), 2)
        self.assertTrue(
            any(
                "espera" in s.payload["texto"].lower()
                for s in SalidaCanal.objects.all()
            )
        )
        self.assertTrue(
            any(
                "intenta" in s.payload["texto"].lower()
                for s in SalidaCanal.objects.all()
            )
        )

    def test_i5_sin_renglones_y_token_invalido(self):
        for i, texto in enumerate(["", "   ", "👍", "hola", "gracias"]):
            self.webhook(f"v{i}", texto, **{"from": f"{i}@c.us"})
        ciclo()
        self.assertFalse(Pedido.objects.exists())
        self.assertEqual(SalidaCanal.objects.filter(tipo="respuesta").count(), 5)
        self.assertTrue(
            all(
                "Escribe tu pedido" in s.payload["texto"]
                for s in SalidaCanal.objects.all()
            )
        )
        self.webhook("pedido", "leche")
        ciclo()
        self.cotizar()
        ciclo()
        self.webhook("aceptar", "ACEPTAR")
        ciclo()
        ultima = SalidaCanal.objects.filter(tipo="respuesta").latest("creado_en")
        self.assertIn("exactamente", ultima.payload["texto"])

    def test_i6_correccion_conserva_renglon_y_resolucion(self):
        self.webhook("m1", "leche")
        ciclo()
        self.cotizar()
        anterior = Pedido.objects.get().renglones.get()
        self.webhook("m2", "CORREGIR: leche; pan")
        ciclo()
        igual = Pedido.objects.get().renglones.get(texto_solicitado="leche")
        self.assertEqual(igual.id, anterior.id)
        self.assertEqual(igual.resolucion, "incluido")
        self.assertEqual(igual.precio_unitario_centavos, 1000)

    def test_i8_reinicio_entre_efecto_y_marca_reusa_clave(self):
        from django.utils import timezone
        from canales.conversacion import procesar_mensaje
        from canales.lector import LectorProcedenciaCanal
        from pedidos.fabrica import obtener_nucleo
        from pedidos.models import ComandoNucleo

        self.webhook("m1", "leche")
        mensaje = MensajeEntrante.objects.select_related("conversacion__sesion").get()
        with patch("canales.conversacion.preparar", side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                procesar_mensaje(
                    mensaje, obtener_nucleo(), LectorProcedenciaCanal(), timezone.now()
                )
        self.assertEqual(Pedido.objects.count(), 1)
        mensaje.refresh_from_db()
        self.assertEqual(mensaje.estado, "pendiente")
        procesar_mensaje(
            mensaje, obtener_nucleo(), LectorProcedenciaCanal(), timezone.now()
        )
        mensaje.refresh_from_db()
        self.assertEqual(mensaje.estado, "procesado")
        self.assertEqual(Pedido.objects.count(), 1)
        self.assertEqual(
            ComandoNucleo.objects.get().command_key, f"registrar:{mensaje.id}"
        )
        self.assertEqual(SalidaCanal.objects.filter(tipo="respuesta").count(), 1)

    def test_i8_intencion_y_cursor_son_atomicos(self):
        from canales.avisos import procesar_avisos
        from canales.lector import LectorProcedenciaCanal
        from canales.models import CursorCanal
        from pedidos.fabrica import obtener_nucleo

        self.webhook("m1", "leche")
        ciclo()
        self.cotizar()
        cursor = CursorCanal.objects.get(consumidor="avisos")
        previo = cursor.cursor

        def fallar_al_guardar(*args, **kwargs):
            self.assertEqual(
                SalidaCanal.objects.filter(tipo="cotizacion_resumen").count(), 1
            )
            raise RuntimeError("fallo al guardar el cursor")

        with patch.object(CursorCanal, "save", side_effect=fallar_al_guardar):
            with self.assertRaisesRegex(RuntimeError, "fallo al guardar el cursor"):
                procesar_avisos(obtener_nucleo(), LectorProcedenciaCanal())
        self.assertFalse(SalidaCanal.objects.filter(tipo="cotizacion_resumen").exists())
        cursor.refresh_from_db()
        self.assertEqual(cursor.cursor, previo)
        procesar_avisos(obtener_nucleo(), LectorProcedenciaCanal())
        cursor.refresh_from_db()
        self.assertNotEqual(cursor.cursor, previo)
        self.assertEqual(
            SalidaCanal.objects.filter(tipo="cotizacion_resumen").count(), 1
        )

    def test_b2_ack_pendiente_con_resumen_anterior(self):
        from django.utils import timezone
        from canales.avisos import procesar_avisos
        from canales.lector import LectorProcedenciaCanal
        from pedidos.fabrica import obtener_nucleo

        self.webhook("m1", "leche")
        ciclo()
        self.cotizar()
        ciclo()
        viejo = SalidaCanal.objects.get(tipo="cotizacion_resumen")
        self.webhook("m2", "CORREGIR: pan")
        ciclo()
        pedido = Pedido.objects.get()
        renglon = pedido.renglones.get()
        revision = operar(
            self.comercio,
            pedido.id,
            "revisar_renglones",
            {
                "command_key": "rev2",
                "expected_version": pedido.version,
                "renglones": [
                    {
                        "renglon_id": str(renglon.id),
                        "descripcion": "Pan",
                        "cantidad": "1",
                        "unidad": "pieza",
                        "precio_unitario_centavos": 500,
                        "resolucion": "incluido",
                    }
                ],
            },
        )
        operar(
            self.comercio,
            pedido.id,
            "publicar_cotizacion",
            {
                "command_key": "pub2",
                "expected_version": revision.data["pedido"].version,
            },
        )
        procesar_avisos(obtener_nucleo(), LectorProcedenciaCanal())
        nuevo = (
            SalidaCanal.objects.filter(tipo="cotizacion_resumen")
            .exclude(pk=viejo.pk)
            .get()
        )
        nuevo.estado = "enviando"
        nuevo.envio_iniciado_en = timezone.now()
        nuevo.save()
        self.webhook("m3", f"ACEPTAR {nuevo.payload['token_resumen']}")
        ciclo()
        mensaje = MensajeEntrante.objects.get(id_mensaje_proveedor="m3")
        self.assertEqual(mensaje.estado, "reintentable")
        self.assertFalse(Aceptacion.objects.exists())
        nuevo.estado, nuevo.id_proveedor, nuevo.enviado_en = (
            "enviada",
            "ack2",
            timezone.now(),
        )
        nuevo.save()
        MensajeEntrante.objects.filter(pk=mensaje.pk).update(
            proximo_intento_en=timezone.now()
        )
        ciclo()
        self.assertEqual(Aceptacion.objects.count(), 1)
        self.assertEqual(
            str(Aceptacion.objects.get().cotizacion_id), nuevo.payload["cotizacion_id"]
        )

    def test_m4_salidas_se_envian_en_orden_de_creacion(self):
        from datetime import timedelta
        from django.utils import timezone
        from canales.models import ConversacionCanal

        self.webhook("m1", "leche")
        ciclo()
        conversacion = ConversacionCanal.objects.get()
        posterior = SalidaCanal.objects.create(
            conversacion=conversacion,
            causa="posterior",
            destinatario=conversacion.chat_id,
            tipo="respuesta",
            payload={"texto": "segundo"},
        )
        anterior = SalidaCanal.objects.create(
            conversacion=conversacion,
            causa="anterior",
            destinatario=conversacion.chat_id,
            tipo="respuesta",
            payload={"texto": "primero"},
        )
        SalidaCanal.objects.filter(pk=anterior.pk).update(
            creado_en=timezone.now() - timedelta(minutes=1)
        )
        with patch.object(
            TransporteFalso, "enviar_texto", side_effect=["uno", "dos"]
        ) as envio:
            ciclo()
        self.assertEqual(
            [llamada.args[2] for llamada in envio.call_args_list],
            ["primero", "segundo"],
        )
        posterior.refresh_from_db()
        self.assertEqual(posterior.id_proveedor, "dos")

    def test_i5_consulta_fallida_no_limpia_ni_crea_pedido(self):
        from unittest.mock import Mock

        from django.utils import timezone

        from canales.conversacion import procesar_mensaje
        from canales.models import ConversacionCanal
        from pedidos.contratos.v1 import CodigoError, ErrorV1, RespuestaV1

        self.webhook("fallo-1", "leche")
        ciclo()
        pedido = Pedido.objects.get()
        self.webhook("fallo-2", "pan")
        mensaje = MensajeEntrante.objects.get(id_mensaje_proveedor="fallo-2")
        nucleo = Mock(ES_SIMULACION=False)
        nucleo.consultar_pedido.return_value = RespuestaV1(
            False, error=ErrorV1(
                CodigoError.SERVICIO_NO_DISPONIBLE, "fallo", retryable=True
            )
        )
        procesar_mensaje(mensaje, nucleo, None, timezone.now())
        mensaje.refresh_from_db()
        self.assertEqual(mensaje.estado, "reintentable")
        self.assertEqual(ConversacionCanal.objects.get().pedido_id_actual, pedido.pk)
        self.assertEqual(Pedido.objects.count(), 1)
        nucleo.registrar_solicitud.assert_not_called()

    @override_settings(PEDIDOS_COBRO_HABILITADO=True, DEMO_MODE="false")
    def test_aceptar_real_reservado_informa_pendiente(self):
        from ambito.tests.soporte import crear_cuenta
        from canales import mensajes
        from pedidos.models import IntentoCobro

        crear_cuenta(self.comercio)
        self.webhook("real-1", "leche")
        ciclo()
        self.cotizar()
        ciclo()
        resumen = SalidaCanal.objects.get(tipo="cotizacion_resumen")
        self.webhook("real-2", f"ACEPTAR {resumen.payload['token_resumen']}")
        ciclo()
        self.assertEqual(IntentoCobro.objects.get().estado, "reservado")
        mensaje = MensajeEntrante.objects.get(id_mensaje_proveedor="real-2")
        salida = SalidaCanal.objects.get(causa=f"mensaje:{mensaje.id}")
        self.assertEqual(salida.payload["texto"], mensajes.PENDIENTE)



@override_settings(WAHA_WEBHOOK_SECRET="prueba", NUCLEO_ADAPTADOR="real")
class IntegracionPagoRealTests(TransactionTestCase):
    setUp = IntegracionRealTests.setUp
    webhook = IntegracionRealTests.webhook
    cotizar = IntegracionRealTests.cotizar

    @override_settings(
        PEDIDOS_COBRO_HABILITADO=True, DEMO_MODE="false", PEY_WEBHOOK_SECRET=SECRETO
    )
    def test_pago_real_no_avanza_preparacion_y_avisa(self):
        from unittest.mock import Mock

        from ambito.tests.soporte import crear_cuenta
        from pedidos.models import IntentoCobro
        from pedidos.servicios.despacho import enviar_intento
        from pey.tipos import QrCreado
        from webhooks.tests.support.pey_webhook import post_firmado

        cuenta = crear_cuenta(self.comercio)
        self.webhook("pago-1", "leche")
        ciclo()
        self.cotizar()
        ciclo()
        resumen = SalidaCanal.objects.get(tipo="cotizacion_resumen")
        self.webhook("pago-2", f"ACEPTAR {resumen.payload['token_resumen']}")
        ciclo()
        intento = IntentoCobro.objects.get()
        puerto = Mock()
        puerto.crear_qr.return_value = QrCreado("qr-prueba", "qr-prueba")
        enviar_intento(intento.pk, puerto)
        cuerpo = json.dumps({
            "type": "codi.qr.payment_received", "amount": 20,
            "transactionId": "pago-real", "codiQrId": "qr-prueba",
            "bankAccountId": cuenta.pey_bank_account_id,
        }, separators=(",", ":"))
        respuesta = post_firmado(self.client, cuerpo, "pago-real")
        self.assertEqual(respuesta.status_code, 200)
        intento.refresh_from_db()
        pedido = Pedido.objects.get()
        self.assertEqual(intento.estado, "pagado")
        self.assertEqual(pedido.preparacion, "pendiente")
        self.assertIsNone(pedido.listo_en)
        self.assertIsNone(pedido.entregado_en)
        ciclo()
        aviso = SalidaCanal.objects.get(tipo="aviso")
        self.assertIn("confirmación del pago", aviso.payload["texto"])
        self.assertNotIn("listo", aviso.payload["texto"].lower())

    @override_settings(
        PEDIDOS_COBRO_HABILITADO=True, DEMO_MODE="false", PEY_WEBHOOK_SECRET=SECRETO
    )
    def test_i5_nuevo_pedido_en_mismo_chat_despues_de_entrega(self):
        from unittest.mock import Mock

        from django.contrib.auth import get_user_model

        from ambito.tests.soporte import crear_cuenta
        from canales import mensajes
        from canales.models import ConversacionCanal
        from pedidos.models import IntentoCobro
        from pedidos.servicios.despacho import enviar_intento
        from pedidos.servicios.entrega import operar as entregar
        from pey.tipos import QrCreado
        from webhooks.tests.support.pey_webhook import post_firmado

        cuenta = crear_cuenta(self.comercio)
        self.webhook("i5-1", "leche")
        ciclo()
        primero = Pedido.objects.get()
        self.webhook("i5-abierto", "pan")
        ciclo()
        self.assertEqual(Pedido.objects.count(), 1)
        mensaje = MensajeEntrante.objects.get(id_mensaje_proveedor="i5-abierto")
        self.assertEqual(
            SalidaCanal.objects.get(causa=f"mensaje:{mensaje.pk}").payload["texto"],
            mensajes.ABIERTO,
        )
        self.cotizar()
        ciclo()
        resumen = SalidaCanal.objects.get(tipo="cotizacion_resumen")
        self.webhook("i5-aceptar", f"ACEPTAR {resumen.payload['token_resumen']}")
        ciclo()
        intento = IntentoCobro.objects.get(pedido=primero)
        puerto = Mock()
        puerto.crear_qr.return_value = QrCreado("i5-qr", "i5-qr")
        enviar_intento(intento.pk, puerto)
        cuerpo = json.dumps(
            {
                "type": "codi.qr.payment_received", "amount": 20,
                "transactionId": "i5-pago", "codiQrId": "i5-qr",
                "bankAccountId": cuenta.pey_bank_account_id,
            }, separators=(",", ":"),
        )
        self.assertEqual(post_firmado(self.client, cuerpo, "i5-pago").status_code, 200)
        intento.refresh_from_db()
        self.assertEqual(intento.estado, "pagado")
        usuario = get_user_model().objects.create_user(username="i5-tendero")
        primero.refresh_from_db()
        listo = entregar(
            self.comercio, primero.pk,
            {"command_key": "i5-listo", "expected_version": primero.version}, usuario,
        )
        self.assertTrue(listo.ok)
        entregado = entregar(
            self.comercio, primero.pk,
            {
                "command_key": "i5-entregado",
                "expected_version": listo.data["pedido"].version,
            },
            usuario, entregado=True,
        )
        self.assertTrue(entregado.ok)
        ciclo()
        avisos_anteriores = set(
            SalidaCanal.objects.filter(tipo="aviso").values_list("pk", flat=True)
        )
        self.assertEqual(len(avisos_anteriores), 3)
        self.webhook("i5-2", "pan")
        ciclo()
        self.assertEqual(Pedido.objects.count(), 2)
        primero.refresh_from_db()
        segundo = Pedido.objects.exclude(pk=primero.pk).get()
        self.assertEqual((primero.estado, primero.abierto), ("cerrado", False))
        self.assertEqual(segundo.renglones.get().texto_solicitado, "pan")
        self.assertEqual(ConversacionCanal.objects.get().pedido_id_actual, segundo.pk)
        self.assertEqual(
            set(SalidaCanal.objects.filter(tipo="aviso").values_list("pk", flat=True)),
            avisos_anteriores,
        )
