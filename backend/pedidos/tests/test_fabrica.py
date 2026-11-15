from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings

from pedidos.contratos.fixtures import LectorFixtureV1
from pedidos.fabrica import obtener_nucleo
from pedidos.nucleo_real import NucleoRealV1


class FabricaTests(SimpleTestCase):
    @override_settings(NUCLEO_ADAPTADOR="real")
    def test_real_usa_lector_inyectado(self):
        lector = LectorFixtureV1()
        with patch("pedidos.fabrica.obtener_lector", return_value=lector):
            nucleo = obtener_nucleo()
        self.assertIsInstance(nucleo, NucleoRealV1)
        self.assertIs(nucleo.lector, lector)

    @override_settings(NUCLEO_ADAPTADOR="stub", NUCLEO_STUB_PERMITIDO=False)
    def test_stub_no_permitido_no_resuelve_lector(self):
        with patch("pedidos.fabrica.obtener_lector") as lector:
            with self.assertRaises(ImproperlyConfigured):
                obtener_nucleo()
            lector.assert_not_called()
