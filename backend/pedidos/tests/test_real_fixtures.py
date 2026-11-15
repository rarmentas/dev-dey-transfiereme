from django.test import TransactionTestCase

from pedidos.contratos.fixtures import LectorFixtureV1
from pedidos.nucleo_real import NucleoRealV1
from pedidos.tests.driver_real import DriverReal
from pedidos.tests.fixtures_v1 import FixturesContratoV1


class RealFixturesTests(FixturesContratoV1, TransactionTestCase):
    def setUp(self):
        self.lector = LectorFixtureV1()
        self.nucleo = NucleoRealV1(self.lector)
        self.driver = DriverReal(self.lector)
        self.addCleanup(self.driver.cerrar)
