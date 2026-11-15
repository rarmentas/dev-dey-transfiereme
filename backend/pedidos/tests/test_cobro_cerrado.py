from unittest.mock import patch

from movimientos.models import Cobro, Movimiento
from pedidos.contratos.v1 import CodigoError
from pedidos.models import ComandoNucleo
from pedidos.tests.soporte_real import CasoReal


class CobroCerradoTests(CasoReal):
    def test_requiere_aceptacion_y_no_escribe_ni_llama_pey(self):
        ctx, _, pedido = self.crear()
        pedido = self.cotizar(ctx, pedido)
        datos = self.datos_aceptacion(ctx, pedido)
        aceptacion = self.nucleo.aceptar_cotizacion(ctx, **datos).data["pedido"]
        cobro = {
            "contrato_version": "1.0",
            "command_key": "cobro",
            "pedido_id": pedido.id,
            "expected_version": aceptacion.version,
            "aceptacion_id": aceptacion.aceptacion.id,
            "canal": "qr_venta",
        }
        antes = ComandoNucleo.objects.count()
        with (
            patch("pey.seleccion.obtener_puerto") as pey,
            patch(
                "pey.desarrollo.AdaptadorDesarrollo.__init__", return_value=None
            ) as dev,
            patch(
                "pey.produccion.AdaptadorProduccion.__init__", return_value=None
            ) as prod,
        ):
            resultado = self.nucleo.solicitar_cobro(ctx, **cobro)
            dev.assert_not_called()
            prod.assert_not_called()
        self.assertEqual(resultado.error.code, CodigoError.PROVEEDOR_NO_DISPONIBLE)
        self.assertFalse(resultado.error.retryable)
        self.assertEqual(resultado.error.next_action, "consultar_pedido")
        pey.assert_not_called()
        self.assertEqual(ComandoNucleo.objects.count(), antes)
        self.assertEqual(Cobro.objects.count(), 0)
        self.assertEqual(Movimiento.objects.count(), 0)
        self.driver.invalidar_cotizacion(pedido.id)
        self.assertEqual(
            self.nucleo.solicitar_cobro(ctx, **cobro).error.code,
            CodigoError.ACEPTACION_REQUERIDA,
        )

    def test_cambio_de_modo_invalida_aceptacion_para_cobro(self):
        ctx, _, pedido = self.crear()
        pedido = self.cotizar(ctx, pedido)
        datos = self.datos_aceptacion(ctx, pedido)
        aceptado = self.nucleo.aceptar_cotizacion(ctx, **datos).data["pedido"]
        self.driver.cambiar_modo(True, "demo-1")
        resultado = self.nucleo.solicitar_cobro(
            ctx,
            contrato_version="1.0",
            command_key="cobro",
            pedido_id=pedido.id,
            expected_version=aceptado.version,
            aceptacion_id=aceptado.aceptacion.id,
            canal="qr_venta",
        )
        self.assertEqual(resultado.error.code, CodigoError.ACEPTACION_REQUERIDA)
