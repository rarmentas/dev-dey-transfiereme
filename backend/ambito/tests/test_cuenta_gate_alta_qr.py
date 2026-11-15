from django.test import TestCase

from ambito.cuenta import cuenta_esta_active
from ambito.exceptions import CuentaNoActiveError
from ambito.models import Comercio
from ambito.tests.soporte import crear_cuenta
from movimientos.cobro_qr import preparar_alta_qr_general
from movimientos.models import Cobro


class CuentaGateAltaQrTests(TestCase):
    def test_pending_bloquea_alta_qr_sin_cobro(self) -> None:
        comercio = Comercio.objects.create(nombre="PENDING")
        crear_cuenta(comercio, estado="pending")
        self.assertFalse(cuenta_esta_active(comercio))
        with self.assertRaises(CuentaNoActiveError):
            preparar_alta_qr_general(comercio)
        self.assertEqual(Cobro.objects.filter(comercio=comercio).count(), 0)

    def test_active_simulado_permite_pasar_el_gate(self) -> None:
        comercio = Comercio.objects.create(nombre="ACTIVE dev")
        crear_cuenta(comercio)
        self.assertTrue(cuenta_esta_active(comercio))
        preparar_alta_qr_general(comercio)
        self.assertEqual(Cobro.objects.count(), 0)
