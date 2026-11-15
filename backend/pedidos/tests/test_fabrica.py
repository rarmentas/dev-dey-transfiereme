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

    @override_settings(NUCLEO_ADAPTADOR="stub", NUCLEO_STUB_PERMITIDO=True)
    def test_stub_rechaza_credenciales_financieras(self) -> None:
        casos = (
            {"PEY_API_KEY": "llave-ficticia", "PEY_ADAPTADOR": "desarrollo"},
            {"PEY_API_KEY": "", "PEY_ADAPTADOR": " Produccion "},
        )
        with patch("pedidos.fabrica.obtener_lector") as lector:
            for caso in casos:
                with self.subTest(caso=caso), override_settings(**caso):
                    with self.assertRaises(ImproperlyConfigured):
                        obtener_nucleo()
            lector.assert_not_called()

    @override_settings(
        NUCLEO_ADAPTADOR="stub",
        NUCLEO_STUB_PERMITIDO=True,
        PEY_API_KEY="",
        PEY_ADAPTADOR="desarrollo",
    )
    def test_stub_sin_credenciales_se_permite(self) -> None:
        with patch("pedidos.fabrica.obtener_lector", return_value=LectorFixtureV1()):
            self.assertTrue(obtener_nucleo().ES_SIMULACION)

    @override_settings(
        NUCLEO_ADAPTADOR="real",
        PEY_API_KEY="llave-ficticia",
        PEY_ADAPTADOR="produccion",
    )
    def test_real_admite_configuracion_financiera(self) -> None:
        with patch("pedidos.fabrica.obtener_lector", return_value=LectorFixtureV1()):
            self.assertIsInstance(obtener_nucleo(), NucleoRealV1)
