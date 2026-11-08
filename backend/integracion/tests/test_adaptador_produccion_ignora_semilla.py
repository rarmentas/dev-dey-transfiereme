from unittest import mock

from django.test import TestCase, override_settings

from ambito.models import Comercio
from integracion.pey.adaptador_produccion import AdaptadorProduccionPeyCuenta
from integracion.pey.fabrica import obtener_adaptador_pey
from integracion.pey.puerto import CODI_STATUS_PENDING

_CLABE_VALIDA = "012180015826225713"


@override_settings(PEY_ADAPTADOR="produccion")
class AdaptadorProduccionIgnoraSemillaTests(TestCase):
    @mock.patch("urllib.request.urlopen")
    def test_semilla_no_autoriza_active(self, urlopen_mock) -> None:
        comercio = Comercio.objects.create(
            nombre="Semilla en prod",
            clabe=_CLABE_VALIDA,
            semilla_active_dev=True,
        )
        adaptador = obtener_adaptador_pey()
        self.assertIsInstance(adaptador, AdaptadorProduccionPeyCuenta)
        resultado = adaptador.consultar_cuenta_por_clabe(comercio)
        self.assertEqual(resultado.codi_status, CODI_STATUS_PENDING)
        urlopen_mock.assert_not_called()
