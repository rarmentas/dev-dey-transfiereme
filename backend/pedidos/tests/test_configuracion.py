from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings

from config.modo import demo_activo, politica_cobro_version, validar_configuracion


class ConfiguracionTests(SimpleTestCase):
    @override_settings(DEMO_MODE="", DEBUG=True, PEDIDOS_COBRO_HABILITADO=False)
    def test_desarrollo_admite_modo_vacio(self) -> None:
        self.assertFalse(demo_activo())
        validar_configuracion()
        self.assertEqual(politica_cobro_version(), "normal-1")

    @override_settings(DEMO_MODE="otro")
    def test_modo_invalido(self) -> None:
        with self.assertRaises(ImproperlyConfigured):
            demo_activo()

    @override_settings(DEMO_MODE="false", PEDIDOS_COBRO_HABILITADO=True)
    def test_cobro_no_disponible(self) -> None:
        with self.assertRaises(ImproperlyConfigured):
            validar_configuracion()

    @override_settings(
        DEBUG=False,
        DEMO_MODE="TrUe",
        NUCLEO_ADAPTADOR="real",
        POLITICA_COBRO_VERSION="demo-1",
        PEDIDOS_COBRO_HABILITADO=False,
        DEMO_PEY_BANK_ACCOUNT_ID="cuenta",
        PEY_ADAPTADOR="produccion",
    )
    def test_demo_exige_configuracion_de_produccion(self) -> None:
        validar_configuracion()
        self.assertTrue(demo_activo())
        with override_settings(DEMO_PEY_BANK_ACCOUNT_ID=""):
            with self.assertRaises(ImproperlyConfigured):
                validar_configuracion()

    @override_settings(
        DEBUG=False,
        DEMO_MODE="",
        PEDIDOS_COBRO_HABILITADO=False,
        NUCLEO_ADAPTADOR="real",
        POLITICA_COBRO_VERSION="normal-1",
    )
    def test_produccion_exige_modo_explicito(self) -> None:
        with self.assertRaises(ImproperlyConfigured):
            validar_configuracion()

    @override_settings(
        DEBUG=False,
        DEMO_MODE="false",
        NUCLEO_ADAPTADOR="real",
        POLITICA_COBRO_VERSION="normal-1",
        PEDIDOS_COBRO_HABILITADO=False,
    )
    def test_produccion_rechaza_stub_y_politica_vacia(self) -> None:
        validar_configuracion()
        with override_settings(NUCLEO_ADAPTADOR="stub"):
            with self.assertRaises(ImproperlyConfigured):
                validar_configuracion()
        with override_settings(POLITICA_COBRO_VERSION=""):
            with self.assertRaises(ImproperlyConfigured):
                validar_configuracion()

    @override_settings(
        DEBUG=True,
        DEMO_MODE="true",
        NUCLEO_ADAPTADOR="real",
        POLITICA_COBRO_VERSION="demo-1",
        PEDIDOS_COBRO_HABILITADO=False,
        DEMO_PEY_BANK_ACCOUNT_ID="cuenta",
        PEY_ADAPTADOR="produccion",
    )
    def test_demo_rechaza_debug(self) -> None:
        with self.assertRaises(ImproperlyConfigured):
            validar_configuracion()
