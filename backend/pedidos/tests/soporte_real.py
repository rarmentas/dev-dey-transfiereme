from django.test import TransactionTestCase

from pedidos.contratos.fixtures import LectorFixtureV1, id_determinista
from pedidos.contratos.v1 import RenglonSolicitadoV1
from pedidos.nucleo_real import NucleoRealV1
from pedidos.tests.driver_real import DriverReal


class CasoReal(TransactionTestCase):
    def setUp(self):
        self.lector = LectorFixtureV1()
        self.nucleo = NucleoRealV1(self.lector)
        self.driver = DriverReal(self.lector)
        self.addCleanup(self.driver.cerrar)

    def crear(self, sufijo=""):
        ctx = self.driver.contexto(sufijo)
        mensaje, llave = self.driver.agregar_mensaje(ctx, "solicitud", 1, "leche")
        datos = {
            "contrato_version": "1.0",
            "command_key": "crear" + sufijo,
            "mensaje_id": mensaje,
            "message_key": llave,
            "secuencia_conversacion": 1,
            "renglones": [
                RenglonSolicitadoV1(id_determinista(ctx.conversacion_id, "r"), "leche")
            ],
        }
        respuesta = self.nucleo.registrar_solicitud(ctx, **datos)
        self.assertTrue(respuesta.ok, respuesta.error)
        return ctx, datos, respuesta.data["pedido"]

    def cotizar(self, ctx, pedido):
        pedido = self.driver.publicar_cotizacion(
            pedido.id,
            [
                {
                    "renglon_id": pedido.renglones[0].renglon_id,
                    "descripcion": "leche",
                    "cantidad": "2",
                    "unidad": "pieza",
                    "precio_unitario_centavos": 1250,
                }
            ],
        )
        self.driver.agregar_resumen(ctx, pedido.cotizacion)
        return pedido

    def datos_aceptacion(self, ctx, pedido):
        cot = pedido.cotizacion
        mensaje, _ = self.driver.agregar_mensaje(
            ctx, "aceptar", 2, "ACEPTAR " + cot.token_resumen
        )
        return {
            "contrato_version": "1.0",
            "command_key": "aceptar",
            "pedido_id": pedido.id,
            "expected_version": pedido.version,
            "cotizacion_id": cot.id,
            "cotizacion_revision": cot.revision,
            "importe_efectivo_mostrado_centavos": cot.importe_efectivo_centavos,
            "politica_cobro_version": cot.politica_cobro_version,
            "mensaje_consentimiento_id": mensaje,
            "token_resumen": cot.token_resumen,
        }
