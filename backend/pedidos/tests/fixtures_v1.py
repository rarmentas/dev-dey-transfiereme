"""Escenarios normativos compartidos por las implementaciones del puerto."""

from abc import ABC, abstractmethod
from decimal import Decimal
from functools import wraps

from pedidos.contratos.fixtures import id_determinista
from pedidos.contratos.v1 import (
    CodigoError,
    ContextoCanalV1,
    ContextoConsumidorV1,
    EstadoPago,
    EstadoPreparacion,
    RenglonSolicitadoV1,
)


def solo_stub(prueba):
    @wraps(prueba)
    def ejecutar(self):
        if not self.nucleo.ES_SIMULACION:
            self.skipTest("MR-2: requiere IntentoCobro/CuentaCobro")
        return prueba(self)

    return ejecutar


class DriverFixtureV1(ABC):
    """Operaciones de preparación que cada implementación debe proporcionar."""

    @abstractmethod
    def contexto(self, sufijo="", comercio="comercio"): ...

    @abstractmethod
    def agregar_mensaje(self, ctx, clave, secuencia, texto, tipo="texto"): ...

    @abstractmethod
    def agregar_resumen(self, ctx, cotizacion): ...

    @abstractmethod
    def publicar_cotizacion(self, pedido_id, renglones): ...

    @abstractmethod
    def invalidar_cotizacion(self, pedido_id): ...

    @abstractmethod
    def cambiar_modo(self, demo, politica): ...

    @abstractmethod
    def cambiar_sesion(self, ctx, sesion, comercio=None): ...

    def despachar(self):
        return None

    def fijar_cuenta(self, estado):
        raise NotImplementedError

    def ocupar_comercio(self, comercio="comercio"):
        raise NotImplementedError

    def liberar_comercio(self, comercio="comercio"):
        raise NotImplementedError

    def forzar_incierto(self):
        raise NotImplementedError

    def confirmar_pago(self, pedido_id, webhook_id):
        raise NotImplementedError

    def webhook_temprano(self, cobro_id, webhook_id):
        raise NotImplementedError

    def marcar_listo(self, pedido_id):
        raise NotImplementedError

    def marcar_entregado(self, pedido_id):
        raise NotImplementedError

    def activar_intento_en_espera(
        self, pedido_id, intento_id, expected_version, command_key
    ):
        raise NotImplementedError

    def contar_llamadas(self):
        raise NotImplementedError

    def reservar_sin_envio(self, pedido_id):
        raise NotImplementedError

    def audio_fallido(self, ctx, mensaje_id):
        raise NotImplementedError


class FixturesContratoV1:
    """Comprueba efectos, resultados y eventos del contrato."""

    def _crear(self, sufijo=""):
        ctx = self.driver.contexto(sufijo)
        mensaje_id, llave = self.driver.agregar_mensaje(ctx, "solicitud", 1, "leche")
        datos = {
            "contrato_version": "1.0",
            "command_key": "solicitud" + sufijo,
            "mensaje_id": mensaje_id,
            "message_key": llave,
            "secuencia_conversacion": 1,
            "renglones": [
                RenglonSolicitadoV1(
                    id_determinista(ctx.conversacion_id, "renglon"), "leche"
                )
            ],
        }
        respuesta = self.nucleo.registrar_solicitud(ctx, **datos)
        self.assertTrue(respuesta.ok, respuesta.error)
        return ctx, datos, respuesta.data["pedido"]

    def _cotizar(self, ctx, pedido):
        pedido = self.driver.publicar_cotizacion(
            pedido.id,
            [
                {
                    "renglon_id": pedido.renglones[0].renglon_id,
                    "descripcion": "leche",
                    "cantidad": Decimal("2"),
                    "unidad": "pieza",
                    "precio_unitario_centavos": 1250,
                }
            ],
        )
        self.driver.agregar_resumen(ctx, pedido.cotizacion)
        return pedido

    def _datos_aceptar(self, ctx, pedido, clave="aceptar"):
        cot = pedido.cotizacion
        mensaje, _ = self.driver.agregar_mensaje(
            ctx, "consentimiento", 2, "ACEPTAR " + cot.token_resumen
        )
        return {
            "contrato_version": "1.0",
            "command_key": clave,
            "pedido_id": pedido.id,
            "expected_version": pedido.version,
            "cotizacion_id": cot.id,
            "cotizacion_revision": cot.revision,
            "importe_efectivo_mostrado_centavos": cot.importe_efectivo_centavos,
            "politica_cobro_version": cot.politica_cobro_version,
            "mensaje_consentimiento_id": mensaje,
            "token_resumen": cot.token_resumen,
        }

    def _aceptar(self, sufijo=""):
        ctx, _, pedido = self._crear(sufijo)
        pedido = self._cotizar(ctx, pedido)
        datos = self._datos_aceptar(ctx, pedido, "aceptar" + sufijo)
        respuesta = self.nucleo.aceptar_cotizacion(ctx, **datos)
        self.assertTrue(respuesta.ok, respuesta.error)
        return ctx, respuesta.data["pedido"], datos

    def _cobrar(self, ctx, pedido, clave="cobrar"):
        datos = {
            "contrato_version": "1.0",
            "command_key": clave,
            "pedido_id": pedido.id,
            "expected_version": pedido.version,
            "aceptacion_id": pedido.aceptacion.id,
            "canal": "qr_venta",
        }
        return datos, self.nucleo.solicitar_cobro(ctx, **datos)

    def _despachar(self, ctx, pedido_id):
        getattr(self.driver, "despachar", lambda: None)()
        return self.nucleo.consultar_pedido(
            ctx, contrato_version="1.0", pedido_id=pedido_id
        ).data["pedido"]

    def _feed(self, ctx, cursor=None):
        return self.nucleo.consultar_eventos(
            ContextoConsumidorV1(ctx.instancia_id, ctx.sesion_id),
            contrato_version="1.0",
            cursor=cursor,
        )

    def test_f01_texto_borrador_id_estable_y_evento_por_cursor(self):
        ctx, datos, pedido = self._crear()
        replay = self.nucleo.registrar_solicitud(ctx, **datos)
        self.assertTrue(replay.replayed)
        self.assertEqual(replay.data["pedido"].id, pedido.id)
        feed = self._feed(ctx)
        self.assertEqual(
            [e.tipo.value for e in feed.data["eventos"]], ["pedido.creado"]
        )
        self.assertEqual(self._feed(ctx, feed.data["next_cursor"]).data["eventos"], [])

    def test_f02_correccion_reemplaza_y_rechaza_version_obsoleta(self):
        ctx, datos, pedido = self._crear()
        mensaje, llave = self.driver.agregar_mensaje(ctx, "correccion", 2, "pan")
        datos.update(
            command_key="correccion",
            pedido_id=pedido.id,
            expected_version=pedido.version,
            mensaje_id=mensaje,
            message_key=llave,
            secuencia_conversacion=2,
            renglones=[RenglonSolicitadoV1(id_determinista("f02", "pan"), "pan")],
        )
        respuesta = self.nucleo.corregir_borrador(ctx, **datos)
        self.assertEqual(
            [r.texto_solicitado for r in respuesta.data["pedido"].renglones], ["pan"]
        )
        datos["command_key"] = "otra"
        self.assertEqual(
            self.nucleo.corregir_borrador(ctx, **datos).error.code,
            CodigoError.VERSION_OBSOLETA,
        )
        self.assertIn(
            "pedido.corregido", [e.tipo.value for e in self._feed(ctx).data["eventos"]]
        )

    def test_f03_cotizacion_normal_2500_centavos(self):
        ctx, _, pedido = self._crear()
        cot = self._cotizar(ctx, pedido).cotizacion
        self.assertEqual(
            (cot.total_comercial_centavos, cot.importe_efectivo_centavos), (2500, 2500)
        )
        self.assertFalse(cot.demo_mode)
        self.assertEqual(cot.renglones[0]["subtotal_centavos"], 2500)

    def test_f04_cotizacion_demo_un_centavo(self):
        self.driver.cambiar_modo(True, "demo-1")
        ctx, _, pedido = self._crear()
        cot = self._cotizar(ctx, pedido).cotizacion
        self.assertEqual(
            (cot.total_comercial_centavos, cot.importe_efectivo_centavos), (2500, 1)
        )
        self.assertTrue(cot.demo_mode)

    def test_f05_aceptacion_repetida_misma_y_otra_clave(self):
        ctx, pedido, datos = self._aceptar()
        replay = self.nucleo.aceptar_cotizacion(ctx, **datos)
        self.assertTrue(replay.replayed)
        datos["command_key"] = "otra"
        otra = self.nucleo.aceptar_cotizacion(ctx, **datos)
        self.assertTrue(otra.ok)
        self.assertTrue(otra.replayed)
        self.assertEqual(otra.data["pedido"].aceptacion.id, pedido.aceptacion.id)
        eventos = [e.tipo.value for e in self._feed(ctx).data["eventos"]]
        self.assertEqual(eventos.count("pedido.aceptado"), 1)

    def test_f06_revision_modo_y_replay_historico(self):
        ctx, pedido, datos = self._aceptar()
        self.driver.cambiar_modo(True, "demo-1")
        self.assertTrue(self.nucleo.aceptar_cotizacion(ctx, **datos).replayed)
        datos["command_key"] = "nueva"
        self.assertEqual(
            self.nucleo.aceptar_cotizacion(ctx, **datos).error.code,
            CodigoError.MODO_CAMBIO,
        )
        self.driver.cambiar_modo(False, "normal-1")
        reservado = self.driver.reservar_sin_envio(pedido.id)
        self.assertEqual(reservado.pago_estado, EstadoPago.RESERVADO)
        self.driver.cambiar_modo(True, "demo-1")
        actual = self.nucleo.consultar_pedido(
            ctx, contrato_version="1.0", pedido_id=pedido.id
        )
        self.assertEqual(actual.data["pedido"].pago_estado, EstadoPago.DESCARTADO)
        self.assertEqual(self.driver.contar_llamadas(), 0)
        ctx2, otro, _ = self._aceptar("-plaza")
        _, cobro = self._cobrar(ctx2, otro, "cobro-plaza")
        self.assertTrue(cobro.ok, cobro.error)
        actual = self._despachar(ctx2, otro.id)
        self.assertEqual(actual.pago_estado, EstadoPago.PENDIENTE)
        self.assertEqual(
            self.nucleo.aceptar_cotizacion(ctx, **datos).error.code,
            CodigoError.REVISION_OBSOLETA,
        )
        actual = self.nucleo.consultar_pedido(
            ctx, contrato_version="1.0", pedido_id=pedido.id
        )
        self.assertIsNone(actual.data["pedido"].aceptacion)

    def test_f07_cuenta_pendiente_sin_llamada(self):
        ctx, pedido, _ = self._aceptar()
        self.driver.fijar_cuenta("pendiente")
        _, respuesta = self._cobrar(ctx, pedido)
        self.assertEqual(respuesta.error.code, CodigoError.CUENTA_NO_ACTIVE)
        self.assertEqual(self.driver.contar_llamadas(), 0)

    def test_f08_espera_y_activacion_explicita_mismo_intento(self):
        ctx1, primero, _ = self._aceptar("1")
        _, cobro1 = self._cobrar(ctx1, primero, "cobro1")
        enviado1 = self._despachar(ctx1, primero.id)
        self.assertEqual(enviado1.pago_estado, EstadoPago.PENDIENTE)
        ctx2, segundo, _ = self._aceptar("2")
        datos, cobro2 = self._cobrar(ctx2, segundo, "cobro2")
        espera = cobro2.data["pedido"]
        self.assertEqual(espera.pago_estado, EstadoPago.EN_ESPERA)
        self.assertIsNone(espera.intento.cobro_id)
        self.assertNotEqual(
            espera.intento.intento_id, enviado1.intento.intento_id
        )
        datos["command_key"] = "cobro2-otra"
        self.driver.confirmar_pago(primero.id, "webhook1")
        repetido = self.nucleo.solicitar_cobro(ctx2, **datos)
        self.assertEqual(repetido.data["pedido"].pago_estado, EstadoPago.EN_ESPERA)
        datos.update(
            command_key="cobro2-distinto",
            canal="notificacion",
            telefono_bancario_confirmado="1234567890",
        )
        self.assertEqual(
            self.nucleo.solicitar_cobro(ctx2, **datos).error.code,
            CodigoError.INTENCION_DISTINTA,
        )
        activado = self.driver.activar_intento_en_espera(
            segundo.id, espera.intento.intento_id, espera.version, "activar"
        )
        self.assertEqual(activado.intento.intento_id, espera.intento.intento_id)
        self.assertEqual(activado.pago_estado, EstadoPago.PENDIENTE)
        self.assertEqual(self.driver.contar_llamadas(), 2)

    def test_f09_incierto_no_reenvia(self):
        ctx, pedido, _ = self._aceptar()
        self.driver.forzar_incierto()
        datos, respuesta = self._cobrar(ctx, pedido)
        actual = self._despachar(ctx, pedido.id)
        self.assertEqual(actual.pago_estado, EstadoPago.INCIERTO)
        datos["command_key"] = "otra"
        self.assertEqual(
            self.nucleo.solicitar_cobro(ctx, **datos).data["pedido"].pago_estado,
            EstadoPago.INCIERTO,
        )
        self.assertEqual(self.driver.contar_llamadas(), 1)

    def test_f10_webhook_repetido_un_evento(self):
        ctx, pedido, _ = self._aceptar()
        self._cobrar(ctx, pedido)
        self._despachar(ctx, pedido.id)
        self.driver.confirmar_pago(pedido.id, "webhook")
        self.driver.confirmar_pago(pedido.id, "webhook")
        eventos = [e.tipo.value for e in self._feed(ctx).data["eventos"]]
        self.assertEqual(eventos.count("pago.confirmado"), 1)

    def test_f11_pago_listo_entregado_separados(self):
        ctx, pedido, _ = self._aceptar()
        self._cobrar(ctx, pedido)
        self._despachar(ctx, pedido.id)
        with self.assertRaises(ValueError):
            self.driver.marcar_listo(pedido.id)
        pagado = self.driver.confirmar_pago(pedido.id, "pago")
        self.assertEqual(pagado.preparacion, EstadoPreparacion.PENDIENTE)
        listo = self.driver.marcar_listo(pedido.id)
        self.assertEqual(listo.preparacion, EstadoPreparacion.LISTO)
        entregado = self.driver.marcar_entregado(pedido.id)
        self.assertEqual(entregado.preparacion, EstadoPreparacion.ENTREGADO)
        self.assertFalse(entregado.abierto)

    def test_f12_contexto_cursor_y_clave_ajenos(self):
        ctx, datos, pedido = self._crear()
        ajeno = ContextoCanalV1(ctx.instancia_id, ctx.sesion_id, "otro", "otro")
        respuesta = self.nucleo.consultar_pedido(
            ajeno, contrato_version="1.0", pedido_id=pedido.id
        )
        self.assertEqual(respuesta.error.code, CodigoError.PEDIDO_NO_ACCESIBLE)
        datos["renglones"] = [RenglonSolicitadoV1(id_determinista("f12", "pan"), "pan")]
        self.assertEqual(
            self.nucleo.registrar_solicitud(ctx, **datos).error.code,
            CodigoError.CLAVE_REUTILIZADA,
        )
        cursor = self._feed(ctx).data["next_cursor"]
        alterado = cursor[:-1] + ("A" if cursor[-1] != "A" else "B")
        self.assertEqual(
            self._feed(ctx, alterado).error.code, CodigoError.CURSOR_INVALIDO
        )
        otro_ctx = self.driver.contexto("-otra-sesion")
        self.driver.cambiar_sesion(otro_ctx, "otra-sesion")
        consumidor = ContextoConsumidorV1(otro_ctx.instancia_id, "otra-sesion")
        respuesta = self.nucleo.consultar_eventos(
            consumidor, contrato_version="1.0", cursor=cursor
        )
        self.assertEqual(respuesta.error.code, CodigoError.CURSOR_INVALIDO)
        self.driver.cambiar_sesion(ctx, "sesion-comercio-ajeno", "comercio-ajeno")
        consumidor = ContextoConsumidorV1(ctx.instancia_id, "sesion-comercio-ajeno")
        respuesta = self.nucleo.consultar_eventos(
            consumidor, contrato_version="1.0", cursor=cursor
        )
        self.assertEqual(respuesta.error.code, CodigoError.CURSOR_INVALIDO)

    def test_f13_audio_fallido_texto_no_pisa_version_nueva(self):
        ctx, _, pedido = self._crear()
        audio, llave_audio = self.driver.agregar_mensaje(
            ctx, "audio", 2, "", tipo="audio"
        )
        self.assertIn("texto", self.driver.audio_fallido(ctx, audio).lower())
        mensaje, llave = self.driver.agregar_mensaje(ctx, "texto", 3, "pan")
        base = {
            "contrato_version": "1.0",
            "pedido_id": pedido.id,
            "expected_version": pedido.version,
            "renglones": [RenglonSolicitadoV1(id_determinista("f13", "pan"), "pan")],
        }
        nuevo = self.nucleo.corregir_borrador(
            ctx,
            **base,
            command_key="texto",
            mensaje_id=mensaje,
            message_key=llave,
            secuencia_conversacion=3,
        )
        self.assertTrue(nuevo.ok)
        atrasado = self.nucleo.corregir_borrador(
            ctx,
            **base,
            command_key="audio",
            mensaje_id=audio,
            message_key=llave_audio,
            secuencia_conversacion=2,
        )
        self.assertEqual(atrasado.error.code, CodigoError.VERSION_OBSOLETA)
        actual = self.nucleo.consultar_pedido(
            ctx, contrato_version="1.0", pedido_id=pedido.id
        )
        self.assertEqual(actual.data["pedido"].renglones[0].texto_solicitado, "pan")

    def test_f14_webhook_temprano_se_reaplica_una_vez(self):
        ctx, pedido, _ = self._aceptar()
        cobro_id = id_determinista(pedido.id, "cobro")
        self.driver.webhook_temprano(cobro_id, "webhook")
        self.driver.webhook_temprano(cobro_id, "webhook")
        _, respuesta = self._cobrar(ctx, pedido)
        self.assertTrue(respuesta.ok, respuesta.error)
        actual = self._despachar(ctx, pedido.id)
        self.assertEqual(actual.pago_estado, EstadoPago.PAGADO)
        self.driver.confirmar_pago(pedido.id, "webhook")
        eventos = [e.tipo.value for e in self._feed(ctx).data["eventos"]]
        self.assertEqual(eventos.count("pago.confirmado"), 1)
