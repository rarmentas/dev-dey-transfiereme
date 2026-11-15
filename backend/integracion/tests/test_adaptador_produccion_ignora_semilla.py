from unittest import mock

from django.test import TestCase, override_settings

from ambito.models import Comercio, CuentaCobro
from ambito.tests.soporte import clabe_valida
from integracion.pey.adaptador_produccion import AdaptadorProduccionPeyCuenta
from integracion.pey.fabrica import obtener_adaptador_pey
from integracion.pey.puerto import CODI_STATUS_PENDING


@override_settings(PEY_ADAPTADOR="produccion")
class AdaptadorProduccionIgnoraSemillaTests(TestCase):
    @mock.patch("urllib.request.urlopen")
    def test_semilla_no_autoriza_active(self, urlopen_mock) -> None:
        comercio = Comercio.objects.create(
            nombre="Semilla en prod",
            semilla_active_dev=True,
        )
        adaptador = obtener_adaptador_pey()
        self.assertIsInstance(adaptador, AdaptadorProduccionPeyCuenta)
        cuenta = CuentaCobro(comercio=comercio, clabe=clabe_valida(1))
        resultado = adaptador.consultar_cuenta(cuenta)
        self.assertEqual(resultado.codi_status, CODI_STATUS_PENDING)
        urlopen_mock.assert_not_called()
