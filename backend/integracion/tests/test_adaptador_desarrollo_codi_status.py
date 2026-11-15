from unittest import mock

from django.test import TestCase

from ambito.models import Comercio, CuentaCobro
from ambito.tests.soporte import crear_cuenta
from integracion.pey.adaptador_desarrollo import AdaptadorDesarrolloPeyCuenta
from integracion.pey.puerto import CODI_STATUS_ACTIVE, CODI_STATUS_PENDING


class AdaptadorDesarrolloCodiStatusTests(TestCase):
    def setUp(self) -> None:
        self.adaptador = AdaptadorDesarrolloPeyCuenta()

    @mock.patch("urllib.request.urlopen")
    def test_sin_clabe_devuelve_pending_sin_http(self, urlopen_mock) -> None:
        comercio = Comercio.objects.create(nombre="Sin CLABE", semilla_active_dev=True)
        cuenta = CuentaCobro(comercio=comercio, clabe="")
        resultado = self.adaptador.consultar_cuenta(cuenta)
        self.assertEqual(resultado.codi_status, CODI_STATUS_PENDING)
        self.assertEqual(resultado.bank_account_id, "")
        urlopen_mock.assert_not_called()

    @mock.patch("urllib.request.urlopen")
    def test_clabe_sin_semilla_devuelve_pending(self, urlopen_mock) -> None:
        comercio = Comercio.objects.create(
            nombre="CLABE sin semilla",
            semilla_active_dev=False,
        )
        cuenta = crear_cuenta(comercio, predeterminada=False)
        resultado = self.adaptador.consultar_cuenta(cuenta)
        self.assertEqual(resultado.codi_status, CODI_STATUS_PENDING)
        urlopen_mock.assert_not_called()

    @mock.patch("urllib.request.urlopen")
    def test_clabe_con_semilla_devuelve_active_simulado(self, urlopen_mock) -> None:
        comercio = Comercio.objects.create(
            nombre="ACTIVE simulado",
            semilla_active_dev=True,
        )
        cuenta = crear_cuenta(comercio, predeterminada=False)
        resultado = self.adaptador.consultar_cuenta(cuenta)
        self.assertEqual(resultado.codi_status, CODI_STATUS_ACTIVE)
        self.assertTrue(resultado.bank_account_id)
        urlopen_mock.assert_not_called()
