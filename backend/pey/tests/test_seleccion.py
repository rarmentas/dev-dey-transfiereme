from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings

from pey.desarrollo import AdaptadorDesarrollo
from pey.produccion import AdaptadorProduccion
from pey.seleccion import modo_adaptador, obtener_puerto


class ObtenerPuertoTests(SimpleTestCase):
    @override_settings(DEBUG=True, PEY_ADAPTADOR="", PEY_API_KEY="")
    def test_debug_sin_valor_usa_desarrollo(self) -> None:
        self.assertIsInstance(obtener_puerto(), AdaptadorDesarrollo)

    @override_settings(DEBUG=True, PEY_ADAPTADOR="", PEY_API_KEY="llave-real")
    def test_debug_con_llave_no_usa_desarrollo(self) -> None:
        with self.assertRaises(ImproperlyConfigured):
            obtener_puerto()

    @override_settings(DEBUG=True, PEY_ADAPTADOR="desarrollo", PEY_API_KEY="llave-real")
    def test_desarrollo_con_llave_no_arranca(self) -> None:
        with self.assertRaises(ImproperlyConfigured):
            obtener_puerto()

    @override_settings(DEBUG=False, PEY_ADAPTADOR="")
    def test_sin_debug_sin_valor_usa_produccion(self) -> None:
        self.assertIsInstance(obtener_puerto(), AdaptadorProduccion)

    @override_settings(DEBUG=False, PEY_ADAPTADOR="desarrollo")
    def test_desarrollo_sin_debug_no_arranca(self) -> None:
        with self.assertRaises(ImproperlyConfigured):
            obtener_puerto()

    @override_settings(DEBUG=True, PEY_ADAPTADOR="sandbox")
    def test_valor_desconocido_no_arranca(self) -> None:
        with self.assertRaises(ImproperlyConfigured):
            obtener_puerto()

    @override_settings(DEBUG=False, PEY_ADAPTADOR="produccion")
    def test_produccion_explicita_sin_debug(self) -> None:
        self.assertIsInstance(obtener_puerto(), AdaptadorProduccion)


class ModoAdaptadorTests(SimpleTestCase):
    @override_settings(DEBUG=True, PEY_ADAPTADOR=" Desarrollo ", PEY_API_KEY="")
    def test_lower_y_strip_eligen_desarrollo(self) -> None:
        self.assertEqual(modo_adaptador(), "desarrollo")
        self.assertIsInstance(obtener_puerto(), AdaptadorDesarrollo)

    @override_settings(DEBUG=False, PEY_ADAPTADOR=" Produccion ", PEY_API_KEY="")
    def test_lower_y_strip_eligen_produccion(self) -> None:
        self.assertEqual(modo_adaptador(), "produccion")
        self.assertIsInstance(obtener_puerto(), AdaptadorProduccion)

    @override_settings(DEBUG=True, PEY_ADAPTADOR="PROD", PEY_API_KEY="")
    def test_lower_no_acepta_un_alias(self) -> None:
        with self.assertRaisesMessage(
            ImproperlyConfigured,
            "PEY_ADAPTADOR debe ser 'desarrollo' o 'produccion'.",
        ):
            modo_adaptador()
