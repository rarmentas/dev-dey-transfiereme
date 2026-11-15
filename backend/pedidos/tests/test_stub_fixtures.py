from django.test import SimpleTestCase

from pedidos.contratos.fixtures import LectorFixtureV1
from pedidos.stub import DriverStubV1, NucleoStubV1
from pedidos.tests.fixtures_v1 import FixturesContratoV1


class StubFixturesTests(FixturesContratoV1, SimpleTestCase):
    def setUp(self):
        self.lector = LectorFixtureV1()
        self.nucleo = NucleoStubV1(self.lector)
        self.driver = DriverStubV1(self.nucleo)

    def test_simulacion_identificada(self):
        self.assertTrue(self.nucleo.ES_SIMULACION)

    def test_correccion_con_secuencia_tardia_es_version_obsoleta(self):
        from pedidos.contratos.v1 import CodigoError

        ctx, datos, pedido = self._crear()
        mensaje, llave = self.driver.agregar_mensaje(ctx, "tardio", 1, "pan")
        datos.update(
            command_key="tardio",
            pedido_id=pedido.id,
            expected_version=pedido.version,
            mensaje_id=mensaje,
            message_key=llave,
            secuencia_conversacion=1,
        )
        respuesta = self.nucleo.corregir_borrador(ctx, **datos)
        self.assertEqual(respuesta.error.code, CodigoError.VERSION_OBSOLETA)
        self.assertEqual(self.nucleo.pedidos[pedido.id].version, pedido.version)
