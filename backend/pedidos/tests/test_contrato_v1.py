from datetime import datetime, timezone
from decimal import Decimal

from django.test import SimpleTestCase

from pedidos.contratos.v1 import (
    CodigoError,
    ContextoCanalV1,
    EstadoPago,
    RenglonSolicitadoV1,
    message_key,
)
from pedidos.contratos.validacion import ErrorContrato, hash_canonico, validar_comando


class ContratoV1Tests(SimpleTestCase):
    def setUp(self):
        self.ctx = ContextoCanalV1("instancia", "sesion", "chat", "cliente")
        self.datos = {
            "contrato_version": "1.0",
            "command_key": "clave",
            "mensaje_id": "11111111-1111-4111-8111-111111111111",
            "message_key": "mensaje",
            "secuencia_conversacion": 1,
            "renglones": [
                RenglonSolicitadoV1(
                    "22222222-2222-4222-8222-222222222222", "leche", Decimal("1.500")
                )
            ],
        }

    def test_rechaza_campo_desconocido(self):
        self.datos["total_centavos"] = 1
        with self.assertRaises(ErrorContrato) as error:
            validar_comando("registrar_solicitud", self.datos)
        self.assertEqual(error.exception.codigo, CodigoError.PAYLOAD_INVALIDO)

    def test_rechaza_version_distinta(self):
        self.datos["contrato_version"] = "2.0"
        with self.assertRaises(ErrorContrato) as error:
            validar_comando("registrar_solicitud", self.datos)
        self.assertEqual(
            error.exception.codigo, CodigoError.VERSION_CONTRATO_NO_SOPORTADA
        )

    def test_rechaza_command_key_vacia(self):
        self.datos["command_key"] = ""
        with self.assertRaises(ErrorContrato):
            validar_comando("registrar_solicitud", self.datos)

    def test_rechaza_renglones_vacios(self):
        self.datos["renglones"] = []
        with self.assertRaises(ErrorContrato):
            validar_comando("registrar_solicitud", self.datos)

    def test_rechaza_cantidad_flotante(self):
        self.datos["renglones"] = [
            {
                "renglon_id": "22222222-2222-4222-8222-222222222222",
                "texto_solicitado": "leche",
                "cantidad_solicitada": 1.5,
            }
        ]
        with self.assertRaises(ErrorContrato):
            validar_comando("registrar_solicitud", self.datos)

    def test_message_key_no_es_ambigua(self):
        self.assertNotEqual(message_key("ab", "c", "d"), message_key("a", "bc", "d"))
        self.assertEqual(message_key("á", "b", "c"), '["á","b","c"]')

    def test_hash_excluye_clave_y_considera_contexto(self):
        huella = hash_canonico("registrar_solicitud", self.datos, self.ctx)
        self.datos["command_key"] = "otra"
        self.assertEqual(
            huella, hash_canonico("registrar_solicitud", self.datos, self.ctx)
        )
        otro = ContextoCanalV1("instancia", "sesion", "otro", "cliente")
        self.assertNotEqual(
            huella, hash_canonico("registrar_solicitud", self.datos, otro)
        )

    def test_serializacion_de_cantidad_y_enum(self):
        self.assertEqual(
            self.datos["renglones"][0].a_dict()["cantidad_solicitada"], "1.500"
        )
        self.assertEqual(EstadoPago.SIN_COBRO.value, "sin_cobro")
        self.assertEqual(
            datetime(2026, 1, 1, tzinfo=timezone.utc).utcoffset().total_seconds(), 0
        )


class SerializacionDTOTests(SimpleTestCase):
    def test_todos_los_dto_son_json_y_preservan_los_campos_del_contrato(self):
        import json
        from datetime import timedelta
        from uuid import UUID

        from pedidos.contratos.v1 import (
            AceptacionDTO,
            CanalCobro,
            CobroDTO,
            ContextoConsumidorV1,
            CotizacionDTO,
            ErrorV1,
            EstadoPedido,
            EstadoPreparacion,
            EventoDTO,
            MensajeProcedenciaDTO,
            PedidoDTO,
            RenglonDTO,
            RespuestaV1,
            ResumenEnviadoDTO,
            TipoEvento,
        )

        fecha = datetime(2026, 1, 1, 6, tzinfo=timezone(timedelta(hours=6)))
        identidad = UUID("11111111-1111-4111-8111-111111111111")
        ctx = ContextoCanalV1("i", "s", "c", "cliente")
        consumidor = ContextoConsumidorV1("i", "s")
        solicitado = RenglonSolicitadoV1(str(identidad), "leche", Decimal("1.250"))
        renglon = RenglonDTO(str(identidad), 1, "leche", Decimal("1.250"), None)
        cot = CotizacionDTO(
            str(identidad), 1, [], 2500, 1, "MXN", True, "demo-1", "P1-R1", fecha
        )
        aceptacion = AceptacionDTO(
            str(identidad), str(identidad), fecha, {"conversacion_id": "c"}
        )
        cobro = CobroDTO(
            str(identidad), None, CanalCobro.QR_VENTA, EstadoPago.EN_ESPERA
        )
        pedido = PedidoDTO(
            str(identidad),
            1,
            2,
            EstadoPedido.ACEPTADO,
            True,
            {"creado_en": fecha},
            "1234",
            [renglon],
            cot,
            1,
            aceptacion,
            EstadoPago.SIN_COBRO,
            EstadoPreparacion.PENDIENTE,
            None,
            True,
        )
        evento = EventoDTO(
            str(identidad),
            1,
            TipoEvento.PEDIDO_CREADO,
            fecha,
            str(identidad),
            1,
            "c",
            None,
            {},
        )
        mensaje = MensajeProcedenciaDTO(
            str(identidad), "key", 1, "texto", "texto", fecha, fecha, True
        )
        resumen = ResumenEnviadoDTO(
            str(identidad),
            "proveedor",
            "enviado",
            str(identidad),
            "P1-R1",
            1,
            2500,
            1,
            True,
            "demo-1",
            "cliente",
            fecha,
            fecha,
        )
        error = ErrorV1(CodigoError.VERSION_OBSOLETA, "actualice")
        exito = RespuestaV1(True, data={"pedido": pedido})
        fallo = RespuestaV1(False, error=error)
        for dto in (
            ctx,
            consumidor,
            solicitado,
            renglon,
            cot,
            aceptacion,
            cobro,
            pedido,
            evento,
            mensaje,
            resumen,
            error,
            exito,
            fallo,
        ):
            with self.subTest(dto=type(dto).__name__):
                self.assertIsInstance(json.loads(json.dumps(dto.a_dict())), dict)
        self.assertEqual(cot.a_dict()["publicada_en"], "2026-01-01T00:00:00Z")
        self.assertEqual(renglon.a_dict()["cantidad_solicitada"], "1.250")
        self.assertEqual(pedido.a_dict()["pago_estado"], "sin_cobro")
        self.assertEqual(pedido.a_dict()["preparacion"], "pendiente")
        self.assertEqual(evento.a_dict()["tipo"], "pedido.creado")
        self.assertEqual(fallo.a_dict()["error"]["code"], "VERSION_OBSOLETA")
        self.assertEqual(
            exito.a_dict()["data"]["pedido"]["cotizacion"]["importe_efectivo_centavos"],
            1,
        )


class PrecedenciaContratoTests(SimpleTestCase):
    from pedidos.tests.fixtures_v1 import FixturesContratoV1

    _crear = FixturesContratoV1._crear
    _cotizar = FixturesContratoV1._cotizar
    _datos_aceptar = FixturesContratoV1._datos_aceptar
    _aceptar = FixturesContratoV1._aceptar

    def setUp(self):
        from pedidos.contratos.fixtures import LectorFixtureV1
        from pedidos.stub import DriverStubV1, NucleoStubV1

        self.lector = LectorFixtureV1()
        self.nucleo = NucleoStubV1(self.lector)
        self.driver = DriverStubV1(self.nucleo)

    def test_validacion_y_procedencia_preceden_replay_historico(self):
        from dataclasses import replace

        ctx, pedido, datos = self._aceptar()
        self.driver.invalidar_cotizacion(pedido.id)
        invalido = dict(datos, contrato_version="2.0")
        self.assertEqual(
            self.nucleo.aceptar_cotizacion(ctx, **invalido).error.code,
            CodigoError.VERSION_CONTRATO_NO_SOPORTADA,
        )
        invalido = dict(datos, campo_ajeno=True)
        self.assertEqual(
            self.nucleo.aceptar_cotizacion(ctx, **invalido).error.code,
            CodigoError.PAYLOAD_INVALIDO,
        )
        mensaje_id = datos["mensaje_consentimiento_id"]
        mensaje = self.lector.mensajes[(ctx, mensaje_id)]
        self.lector.mensajes[(ctx, mensaje_id)] = replace(
            mensaje, origen_autenticado=False
        )
        self.assertEqual(
            self.nucleo.aceptar_cotizacion(ctx, **datos).error.code,
            CodigoError.CONTEXTO_INVALIDO,
        )
        self.lector.mensajes[(ctx, mensaje_id)] = mensaje
        replay = self.nucleo.aceptar_cotizacion(ctx, **datos)
        self.assertTrue(replay.replayed)
        self.assertIsNone(
            self.nucleo.consultar_pedido(
                ctx, contrato_version="1.0", pedido_id=pedido.id
            )
            .data["pedido"]
            .aceptacion
        )

    def test_consentimiento_exige_texto_token_y_resumen_enviado(self):
        from dataclasses import replace

        ctx, _, pedido = self._crear()
        pedido = self._cotizar(ctx, pedido)
        datos = self._datos_aceptar(ctx, pedido)
        clave = (ctx, datos["mensaje_consentimiento_id"])
        original = self.lector.mensajes[clave]
        for mensaje in (
            replace(original, texto_normalizado="sí"),
            replace(original, tipo="audio"),
        ):
            self.lector.mensajes[clave] = mensaje
            self.assertEqual(
                self.nucleo.aceptar_cotizacion(ctx, **datos).error.code,
                CodigoError.ACEPTACION_REQUERIDA,
            )
        self.lector.mensajes[clave] = original
        resumen_clave = (ctx, pedido.cotizacion.id)
        resumen = self.lector.resumenes[resumen_clave]
        self.lector.resumenes[resumen_clave] = replace(
            resumen, estado="preparado", enviado_en=None
        )
        respuesta = self.nucleo.aceptar_cotizacion(ctx, **datos)
        self.assertEqual(respuesta.error.code, CodigoError.ACEPTACION_REQUERIDA)
        self.assertTrue(respuesta.error.retryable)
        self.lector.resumenes[resumen_clave] = resumen
        self.assertTrue(self.nucleo.aceptar_cotizacion(ctx, **datos).ok)


class DecoradorFixturesTests(SimpleTestCase):
    def test_siete_escenarios_mr2_hacen_skip_explicito_en_real(self):
        import unittest

        from pedidos.tests.fixtures_v1 import FixturesContratoV1

        class NucleoReal:
            ES_SIMULACION = False

        class PruebaReal(FixturesContratoV1, unittest.TestCase):
            nucleo = NucleoReal()

        metodos = [
            nombre
            for nombre in dir(PruebaReal)
            if nombre.startswith(
                (
                    "test_f07_",
                    "test_f08_",
                    "test_f09_",
                    "test_f10_",
                    "test_f11_",
                    "test_f13_",
                    "test_f14_",
                )
            )
        ]
        resultado = unittest.TestResult()
        unittest.TestSuite(PruebaReal(nombre) for nombre in metodos).run(resultado)
        self.assertEqual(resultado.testsRun, 7)
        self.assertEqual(len(resultado.skipped), 7)
        self.assertTrue(all("MR-2" in motivo for _, motivo in resultado.skipped))
