from unittest import mock

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, TestCase, override_settings

from ambito.cuenta_sync import sincronizar_codi_status
from ambito.models import Comercio
from integracion.pey.adaptador_desarrollo import AdaptadorDesarrolloPeyCuenta
from integracion.pey.adaptador_produccion import AdaptadorProduccionPeyCuenta
from integracion.pey.fabrica import obtener_adaptador_pey

_CLABE_VALIDA = "012180015826225713"


class ObtenerAdaptadorPeyTests(SimpleTestCase):
    @override_settings(DEBUG=True, PEY_ADAPTADOR="", PEY_API_KEY="")
    def test_debug_sin_valor_usa_desarrollo(self) -> None:
        self.assertIsInstance(obtener_adaptador_pey(), AdaptadorDesarrolloPeyCuenta)

    @override_settings(DEBUG=False, PEY_ADAPTADOR="", PEY_API_KEY="")
    def test_sin_debug_sin_valor_usa_produccion(self) -> None:
        self.assertIsInstance(obtener_adaptador_pey(), AdaptadorProduccionPeyCuenta)

    @override_settings(DEBUG=False, PEY_ADAPTADOR="desarrollo", PEY_API_KEY="")
    def test_desarrollo_sin_debug_no_arranca(self) -> None:
        with self.assertRaisesMessage(
            ImproperlyConfigured,
            "PEY_ADAPTADOR=desarrollo solo se permite con DEBUG.",
        ):
            obtener_adaptador_pey()

    @override_settings(DEBUG=True, PEY_ADAPTADOR="prod", PEY_API_KEY="")
    def test_valor_desconocido_con_debug_no_arranca(self) -> None:
        with self.assertRaisesMessage(
            ImproperlyConfigured,
            "PEY_ADAPTADOR debe ser 'desarrollo' o 'produccion'.",
        ):
            obtener_adaptador_pey()

    @override_settings(DEBUG=False, PEY_ADAPTADOR="prod", PEY_API_KEY="")
    def test_valor_desconocido_sin_debug_no_arranca(self) -> None:
        with self.assertRaisesMessage(
            ImproperlyConfigured,
            "PEY_ADAPTADOR debe ser 'desarrollo' o 'produccion'.",
        ):
            obtener_adaptador_pey()

    @override_settings(DEBUG=True, PEY_ADAPTADOR="desarrollo", PEY_API_KEY="llave")
    def test_desarrollo_con_llave_no_arranca(self) -> None:
        with self.assertRaisesMessage(
            ImproperlyConfigured,
            "PEY_ADAPTADOR=desarrollo no admite PEY_API_KEY.",
        ):
            obtener_adaptador_pey()

    @override_settings(DEBUG=False, PEY_ADAPTADOR=" Produccion ", PEY_API_KEY="")
    def test_produccion_con_espacios_y_mayusculas(self) -> None:
        self.assertIsInstance(obtener_adaptador_pey(), AdaptadorProduccionPeyCuenta)


class SincronizarNoPersisteActiveConTypoTests(TestCase):
    @override_settings(DEBUG=False, PEY_ADAPTADOR="prod", PEY_API_KEY="")
    @mock.patch("urllib.request.urlopen")
    def test_typo_no_deja_el_comercio_active(self, urlopen_mock) -> None:
        comercio = Comercio.objects.create(
            nombre="Semilla con typo",
            clabe=_CLABE_VALIDA,
            semilla_active_dev=True,
        )
        with self.assertRaises(ImproperlyConfigured):
            sincronizar_codi_status(comercio)
        comercio.refresh_from_db()
        self.assertNotEqual(comercio.pey_codi_status, Comercio.PeyCodiStatus.ACTIVE)
        self.assertIsNone(comercio.pey_codi_status_actualizado_en)
        urlopen_mock.assert_not_called()
