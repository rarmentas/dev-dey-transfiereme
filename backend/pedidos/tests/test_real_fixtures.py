from django.test import TransactionTestCase, override_settings

from webhooks.tests.support.pey_webhook import SECRETO

from pedidos.contratos.fixtures import LectorFixtureV1
from pedidos.nucleo_real import NucleoRealV1
from pedidos.tests.driver_real import DriverReal
from pedidos.tests.fixtures_v1 import FixturesContratoV1


@override_settings(
    PEDIDOS_COBRO_HABILITADO=True,
    PEY_WEBHOOK_SECRET=SECRETO,
)
class RealFixturesTests(FixturesContratoV1, TransactionTestCase):
    def setUp(self):
        self.lector = LectorFixtureV1()
        self.nucleo = NucleoRealV1(self.lector)
        self.driver = DriverReal(self.lector, cobros=True)
        self.addCleanup(self.driver.cerrar)
