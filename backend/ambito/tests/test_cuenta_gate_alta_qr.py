from django.test import TestCase, override_settings

from ambito.cuenta import cuenta_esta_active
from ambito.cuenta_sync import sincronizar_codi_status
from ambito.exceptions import CuentaNoActiveError
from ambito.models import Comercio
from movimientos.cobro_qr import preparar_alta_qr_general
from movimientos.models import Cobro

_CLABE_VALIDA = "012180015826225713"


@override_settings(PEY_ADAPTADOR="desarrollo")
class CuentaGateAltaQrTests(TestCase):
    def test_pending_bloquea_alta_qr_sin_cobro(self) -> None:
        comercio = Comercio.objects.create(
            nombre="PENDING",
            clabe=_CLABE_VALIDA,
            semilla_active_dev=False,
        )
        sincronizar_codi_status(comercio)
        comercio.refresh_from_db()
        self.assertFalse(cuenta_esta_active(comercio))
        with self.assertRaises(CuentaNoActiveError):
            preparar_alta_qr_general(comercio)
        self.assertEqual(Cobro.objects.filter(comercio=comercio).count(), 0)

    def test_active_simulado_permite_pasar_el_gate(self) -> None:
        comercio = Comercio.objects.create(
            nombre="ACTIVE dev",
            clabe=_CLABE_VALIDA,
            semilla_active_dev=True,
        )
        sincronizar_codi_status(comercio)
        comercio.refresh_from_db()
        self.assertTrue(cuenta_esta_active(comercio))
        preparar_alta_qr_general(comercio)
        self.assertEqual(Cobro.objects.count(), 0)
