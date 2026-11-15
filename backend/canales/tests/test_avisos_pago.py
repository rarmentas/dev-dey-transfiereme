"""Garantías de avisos y respuestas de cobro."""

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from django.test import TransactionTestCase
from django.utils import timezone

from ambito.models import Comercio
from canales import mensajes
from canales.avisos import procesar_avisos
from canales.conversacion import procesar_mensaje
from canales.models import (
    ConversacionCanal,
    CursorCanal,
    MensajeEntrante,
    SalidaCanal,
    SesionCanal,
)
from canales.salidas import enviar, recuperar_abandonadas
from pedidos.contratos.v1 import TipoEvento
from pedidos.models import IntentoCobro


class AvisosPagoTests(TransactionTestCase):
    def setUp(self):
        comercio = Comercio.objects.create(nombre="Tienda")
        self.sesion = SesionCanal.objects.create(
            instancia_id="instancia", sesion_id="sesion", comercio=comercio
        )
        self.conversacion = ConversacionCanal.objects.create(
            sesion=self.sesion, chat_id="chat", cliente_externo_id="cliente"
        )
        self.evento = SimpleNamespace(
            tipo=TipoEvento.PAGO_CONFIRMADO,
            evento_id=str(uuid4()),
            conversacion_id=str(self.conversacion.pk),
            pedido_id=str(uuid4()),
            snapshot={
                "pedido_numero": 42,
                "importe_efectivo_centavos": 1,
                "total_comercial_centavos": 2500,
                "demo_mode": True,
                "clabe": "123456789012345678",
                "telefono": "5555555555",
            },
        )
        self.nucleo = Mock(ES_SIMULACION=False)
        self.nucleo.consultar_eventos.return_value = SimpleNamespace(
            ok=True, data={"eventos": [self.evento], "next_cursor": "siguiente"}
        )

    def procesar(self):
        procesar_avisos(self.nucleo, None)

    def test_evento_repetido_una_sola_intencion(self):
        self.procesar()
        self.procesar()
        salida = SalidaCanal.objects.get()
        self.assertEqual(salida.causa, f"evento:{self.evento.evento_id}")
        self.assertEqual(salida.tipo, "aviso")
        self.assertEqual(SalidaCanal.objects.count(), 1)
        self.assertEqual(CursorCanal.objects.get().cursor, "siguiente")

    def test_cancelacion_prepara_whatsapp_con_texto_exacto(self):
        self.evento.tipo = TipoEvento.PEDIDO_CANCELADO
        self.procesar()
        salida = SalidaCanal.objects.get()
        self.assertEqual(salida.destinatario, "cliente")
        self.assertEqual(
            salida.payload["texto"],
            "Tu pedido #42 fue cancelado por el comercio. Puedes enviar uno nuevo.",
        )
        self.procesar()
        self.assertEqual(SalidaCanal.objects.count(), 1)

    def test_cursor_e_intencion_son_atomicos(self):
        CursorCanal.objects.create(consumidor="avisos", sesion=self.sesion)

        def falla_despues(cursor, *args, **kwargs):
            self.assertEqual(SalidaCanal.objects.count(), 1)
            self.assertEqual(cursor.cursor, "siguiente")
            raise RuntimeError("fallo al guardar cursor")

        with patch.object(
            CursorCanal, "save", autospec=True, side_effect=falla_despues
        ):
            with self.assertRaises(RuntimeError):
                self.procesar()
        self.assertFalse(SalidaCanal.objects.exists())
        self.assertEqual(CursorCanal.objects.get().cursor, "")
        self.procesar()
        self.assertEqual(SalidaCanal.objects.count(), 1)
        self.assertEqual(CursorCanal.objects.get().cursor, "siguiente")

    def test_waha_caido_recupera_desde_cursor(self):
        self.procesar()
        salida = SalidaCanal.objects.get()
        self.assertEqual(salida.estado, "preparada")
        transporte = Mock()
        transporte.enviar_texto.return_value = "ack"
        enviar(salida.pk, transporte)
        salida.refresh_from_db()
        self.assertEqual(salida.estado, "enviada")
        self.assertEqual(transporte.enviar_texto.call_count, 1)

    def test_crash_entre_envio_y_ack_no_reenvia_ni_recrea_cobro(self):
        self.procesar()
        salida = SalidaCanal.objects.get()
        transporte = Mock()
        transporte.enviar_texto.side_effect = KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            enviar(salida.pk, transporte)
        SalidaCanal.objects.filter(pk=salida.pk).update(
            envio_iniciado_en=timezone.now() - timedelta(seconds=61)
        )
        self.assertEqual(recuperar_abandonadas(), 1)
        enviar(salida.pk, transporte)
        self.procesar()
        salida.refresh_from_db()
        self.assertEqual(salida.estado, "incierta")
        self.assertEqual(transporte.enviar_texto.call_count, 1)
        self.assertEqual(SalidaCanal.objects.count(), 1)
        self.assertFalse(IntentoCobro.objects.exists())

    def test_aviso_sin_clabe_ni_datos_de_otra_conversacion(self):
        otra = ConversacionCanal.objects.create(
            sesion=self.sesion, chat_id="otro", cliente_externo_id="ajeno"
        )
        self.procesar()
        salida = SalidaCanal.objects.get()
        self.assertEqual(salida.conversacion, self.conversacion)
        self.assertNotEqual(salida.conversacion, otra)
        self.assertIn("42", salida.payload["texto"])
        self.assertIn("$0.01", salida.payload["texto"])
        self.assertIn("$25.00", salida.payload["texto"])
        self.assertNotIn("123456789012345678", str(salida.payload))
        self.assertNotIn("5555555555", str(salida.payload))
        self.nucleo.consultar_pedido.assert_not_called()

    def test_avisos_listo_y_entregado(self):
        for tipo, palabra in (
            (TipoEvento.PEDIDO_LISTO, "listo"),
            (TipoEvento.PEDIDO_ENTREGADO, "entregado"),
        ):
            self.evento.tipo = tipo
            self.evento.evento_id = str(uuid4())
            self.procesar()
            self.assertIn(
                palabra,
                SalidaCanal.objects.get(
                    causa=f"evento:{self.evento.evento_id}"
                ).payload["texto"],
            )

    def test_pagado_no_marca_listo_ni_entregado(self):
        self.procesar()
        texto = SalidaCanal.objects.get().payload["texto"].lower()
        self.assertNotIn("listo", texto)
        self.assertNotIn("entregado", texto)
        self.nucleo.marcar_listo.assert_not_called()
        self.nucleo.marcar_entregado.assert_not_called()

    def test_ya_pague_no_confirma(self):
        self.conversacion.pedido_id_actual = uuid4()
        self.conversacion.save()
        mensaje = MensajeEntrante.objects.create(
            conversacion=self.conversacion,
            instancia_id="instancia",
            sesion_id="sesion",
            id_mensaje_proveedor="m1",
            hash_payload="x",
            secuencia=1,
            tipo="texto",
            texto="ya pagué",
        )
        pedido = SimpleNamespace(
            id=str(self.conversacion.pedido_id_actual),
            numero=42,
            pago_estado=SimpleNamespace(value="pendiente"),
        )
        self.nucleo.consultar_pedido.return_value = SimpleNamespace(
            ok=True, data={"pedido": pedido}
        )
        procesar_mensaje(mensaje, self.nucleo, None, timezone.now())
        self.assertEqual(
            SalidaCanal.objects.get().payload["texto"], mensajes.AUN_SIN_PAGO
        )
        self.nucleo.solicitar_cobro.assert_not_called()
        self.nucleo.confirmar_pago.assert_not_called()

    def test_aceptar_mapea_estados_y_errores(self):
        self.conversacion.pedido_id_actual = uuid4()
        self.conversacion.save()
        SalidaCanal.objects.create(
            conversacion=self.conversacion,
            causa="resumen",
            destinatario="cliente",
            tipo="cotizacion_resumen",
            estado="enviada",
            id_proveedor="ack",
            envio_iniciado_en=timezone.now(),
            payload={
                "token_resumen": "ABC",
                "pedido_version": 1,
                "cotizacion_id": "cot",
                "cotizacion_revision": 1,
                "importe_efectivo_centavos": 100,
                "politica_cobro_version": "v1",
            },
        )
        pedido = SimpleNamespace(
            id=str(self.conversacion.pedido_id_actual),
            version=2,
            aceptacion=SimpleNamespace(id="aceptacion"),
        )
        self.nucleo.aceptar_cotizacion.return_value = SimpleNamespace(
            ok=True, data={"pedido": pedido}
        )
        casos = {
            "en_espera": mensajes.ESPERA,
            "reservado": mensajes.PENDIENTE,
            "enviando": mensajes.PENDIENTE,
            "pendiente": mensajes.PENDIENTE,
            "incierto": mensajes.INCIERTO,
            "descartado": mensajes.OBSOLETA,
            "CUENTA_NO_ACTIVE": mensajes.COBRO_NO_DISPONIBLE,
            "DEMO_DESTINO_NO_PERMITIDO": mensajes.COBRO_NO_DISPONIBLE,
            "PROVEEDOR_NO_DISPONIBLE": mensajes.ACEPTADO,
        }
        for indice, (estado, esperado) in enumerate(casos.items(), 1):
            with self.subTest(estado=estado):
                mensaje = MensajeEntrante.objects.create(
                    conversacion=self.conversacion,
                    instancia_id="instancia",
                    sesion_id="sesion",
                    id_mensaje_proveedor=f"a{indice}",
                    hash_payload="x",
                    secuencia=indice,
                    tipo="texto",
                    texto="ACEPTAR ABC",
                )
                if estado.isupper():
                    resultado = SimpleNamespace(
                        ok=False,
                        error=SimpleNamespace(
                            retryable=False, code=SimpleNamespace(value=estado)
                        ),
                    )
                else:
                    pedido.pago_estado = SimpleNamespace(value=estado)
                    resultado = SimpleNamespace(ok=True, data={"pedido": pedido})
                self.nucleo.solicitar_cobro.return_value = resultado
                procesar_mensaje(mensaje, self.nucleo, None, timezone.now())
                salida = SalidaCanal.objects.get(causa=f"mensaje:{mensaje.id}")
                self.assertEqual(salida.payload["texto"], esperado)

    def test_ya_pague_consulta_estado_y_fallo_de_consulta(self):
        self.conversacion.pedido_id_actual = uuid4()
        self.conversacion.save()
        for indice, (estado, esperado) in enumerate(
            (
                ("pagado", "confirmación del pago"),
                ("incierto", mensajes.INCIERTO),
                ("sin_cobro", mensajes.AUN_SIN_PAGO),
            ),
            1,
        ):
            mensaje = MensajeEntrante.objects.create(
                conversacion=self.conversacion,
                instancia_id="instancia",
                sesion_id="sesion",
                id_mensaje_proveedor=f"p{indice}",
                hash_payload="x",
                secuencia=indice,
                tipo="texto",
                texto="pague",
            )
            pedido = SimpleNamespace(
                id=str(self.conversacion.pedido_id_actual),
                numero=42,
                pago_estado=SimpleNamespace(value=estado),
            )
            self.nucleo.consultar_pedido.return_value = SimpleNamespace(
                ok=True, data={"pedido": pedido}
            )
            procesar_mensaje(mensaje, self.nucleo, None, timezone.now())
            salida = SalidaCanal.objects.get(causa=f"mensaje:{mensaje.id}")
            self.assertIn(esperado, salida.payload["texto"])
        self.nucleo.solicitar_cobro.assert_not_called()

    def test_evento_ajeno_y_snapshot_sin_importes(self):
        otra_sesion = SesionCanal.objects.create(
            instancia_id="otra", sesion_id="otra", comercio=self.sesion.comercio
        )
        ajena = ConversacionCanal.objects.create(
            sesion=otra_sesion, chat_id="ajeno", cliente_externo_id="ajeno"
        )
        self.evento.conversacion_id = str(ajena.pk)
        self.evento.snapshot = {"pedido_numero": None}
        self.procesar()
        self.assertEqual(SalidaCanal.objects.count(), 1)
        salida = SalidaCanal.objects.get()
        self.assertEqual(salida.conversacion, ajena)
        self.assertNotIn("$", salida.payload["texto"])
        salida.delete()
        self.nucleo.consultar_eventos.side_effect = [
            SimpleNamespace(
                ok=True, data={"eventos": [self.evento], "next_cursor": "otro"}
            ),
            SimpleNamespace(ok=True, data={"eventos": [], "next_cursor": "otro"}),
        ]
        self.procesar()
        self.assertFalse(SalidaCanal.objects.exists())

    def test_audio_fallido_repetido_no_duplica_respuesta(self):
        from pedidos.contratos.fixtures import LectorFixtureV1
        from pedidos.tests.driver_real import DriverReal

        driver = DriverReal(LectorFixtureV1())
        self.addCleanup(driver.cerrar)
        ctx = driver.contexto("-audio")
        audio, _ = driver.agregar_mensaje(ctx, "audio", 2, "", tipo="audio")
        primero = driver.audio_fallido(ctx, audio)
        self.assertEqual(primero, mensajes.AUDIO_FALLIDO)
        self.assertEqual(driver.audio_fallido(ctx, audio), primero)
        self.assertEqual(
            SalidaCanal.objects.filter(causa=f"mensaje:{audio}").count(), 1
        )

    def test_todos_los_avisos_usan_solo_snapshot_y_tipo_correcto(self):
        casos = (
            (TipoEvento.PAGO_CONFIRMADO, mensajes.PAGADO),
            (TipoEvento.PEDIDO_LISTO, mensajes.LISTO),
            (TipoEvento.PEDIDO_ENTREGADO, mensajes.ENTREGADO),
            (TipoEvento.COBRO_INCIERTO, mensajes.COBRO_INCIERTO),
            (TipoEvento.COBRO_RECHAZADO, mensajes.COBRO_RECHAZADO),
            (TipoEvento.COBRO_VENCIDO, mensajes.COBRO_VENCIDO),
            (TipoEvento.COBRO_DESCARTADO, mensajes.COBRO_DESCARTADO),
        )
        for tipo, plantilla in casos:
            with self.subTest(tipo=tipo):
                self.evento.tipo = tipo
                self.evento.evento_id = str(uuid4())
                self.procesar()
                salida = SalidaCanal.objects.get(
                    causa=f"evento:{self.evento.evento_id}"
                )
                self.assertEqual(
                    salida.payload,
                    {
                        "texto": plantilla.format(pedido_numero=42)
                        + " Importe: $0.01. Total comercial: $25.00."
                    },
                )
                self.assertEqual(salida.conversacion, self.conversacion)
        self.nucleo.consultar_pedido.assert_not_called()

    def test_comercio_y_cliente_ajenos_no_reciben_aviso(self):
        comercio_ajeno = Comercio.objects.create(nombre="Otro")
        sesion_ajena = SesionCanal.objects.create(
            instancia_id="otra", sesion_id="otra", comercio=comercio_ajeno
        )
        ajena = ConversacionCanal.objects.create(
            sesion=sesion_ajena, chat_id="ajeno", cliente_externo_id="ajeno"
        )
        otro_cliente = ConversacionCanal.objects.create(
            sesion=self.sesion, chat_id="otro", cliente_externo_id="otro"
        )

        def feed(ctx, **kwargs):
            eventos = [self.evento] if ctx.sesion_id == "sesion" else []
            return SimpleNamespace(
                ok=True, data={"eventos": eventos, "next_cursor": "nuevo"}
            )

        self.nucleo.consultar_eventos.side_effect = feed
        self.procesar()
        self.assertEqual(SalidaCanal.objects.count(), 1)
        self.assertEqual(SalidaCanal.objects.get().conversacion, self.conversacion)
        self.assertFalse(
            SalidaCanal.objects.filter(conversacion__in=[ajena, otro_cliente]).exists()
        )

    def test_snapshot_sin_demo_ni_importe_y_con_importe_cero(self):
        self.evento.snapshot = {
            "pedido_numero": 0,
            "importe_efectivo_centavos": 0,
            "total_comercial_centavos": 9999,
            "demo_mode": False,
        }
        self.procesar()
        self.assertEqual(
            SalidaCanal.objects.get().payload["texto"],
            mensajes.PAGADO.format(pedido_numero=0) + " Importe: $0.00.",
        )
        self.evento.evento_id = str(uuid4())
        self.evento.snapshot = {}
        self.procesar()
        self.assertEqual(
            SalidaCanal.objects.get(causa=f"evento:{self.evento.evento_id}").payload,
            {"texto": mensajes.PAGADO.format(pedido_numero="")},
        )
