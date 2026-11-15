from pedidos.contratos.v1 import CodigoError, ContextoConsumidorV1
from pedidos.tests.soporte_real import CasoReal


class CursorTests(CasoReal):
    def test_cursor_aisla_sesion_y_valida_firma(self):
        ctx, _, _ = self.crear()
        consumidor = ContextoConsumidorV1(ctx.instancia_id, ctx.sesion_id)
        feed = self.nucleo.consultar_eventos(
            consumidor, contrato_version="1.0", cursor=None, limite=1
        )
        self.assertEqual(len(feed.data["eventos"]), 1)
        cursor = feed.data["next_cursor"]
        self.assertEqual(
            self.nucleo.consultar_eventos(
                consumidor, contrato_version="1.0", cursor=cursor
            ).data["eventos"],
            [],
        )
        self.assertEqual(
            self.nucleo.consultar_eventos(
                consumidor, contrato_version="1.0", cursor=cursor + "x"
            ).error.code,
            CodigoError.CURSOR_INVALIDO,
        )
        self.driver.cambiar_sesion(ctx, "otra")
        otro = ContextoConsumidorV1(ctx.instancia_id, "otra")
        self.assertEqual(
            self.nucleo.consultar_eventos(
                otro, contrato_version="1.0", cursor=cursor
            ).error.code,
            CodigoError.CURSOR_INVALIDO,
        )
        self.assertEqual(
            self.nucleo.consultar_eventos(
                otro, contrato_version="1.0", cursor=None
            ).data["eventos"],
            [],
        )

    def test_cursor_avanza_sobre_eventos_de_otra_sesion(self):
        ctx, _, _ = self.crear()
        otro = self.driver.contexto("-otra")
        self.driver.cambiar_sesion(otro, "otra")
        from pedidos.contratos.fixtures import id_determinista
        from pedidos.contratos.v1 import ContextoCanalV1, RenglonSolicitadoV1

        otro = ContextoCanalV1(
            otro.instancia_id, "otra", otro.conversacion_id, otro.cliente_externo_id
        )
        mensaje, llave = self.driver.agregar_mensaje(otro, "solicitud", 1, "pan")
        resultado = self.nucleo.registrar_solicitud(
            otro,
            contrato_version="1.0",
            command_key="otro",
            mensaje_id=mensaje,
            message_key=llave,
            secuencia_conversacion=1,
            renglones=[RenglonSolicitadoV1(id_determinista("otro", "r"), "pan")],
        )
        self.assertTrue(resultado.ok, resultado.error)
        consumidor = ContextoConsumidorV1(ctx.instancia_id, ctx.sesion_id)
        pagina = self.nucleo.consultar_eventos(
            consumidor, contrato_version="1.0", cursor=None, limite=1
        )
        self.assertEqual(
            [evento.tipo.value for evento in pagina.data["eventos"]], ["pedido.creado"]
        )
        self.assertFalse(pagina.data["has_more"])
        self.assertEqual(
            self.nucleo.consultar_eventos(
                consumidor, contrato_version="1.0", cursor=pagina.data["next_cursor"]
            ).data["eventos"],
            [],
        )
