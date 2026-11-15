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
