"""Guardas de emisión que también aplican al invocar servicios."""

from decimal import Decimal
from unittest.mock import Mock, patch

from ambito.tests.soporte import crear_comercio_con_cuenta_activa, crear_cuenta
from django.test import TestCase, override_settings
from ventas.servicio import crear_venta_notificacion, crear_venta_qr

from movimientos.alta_qr_general import alta_qr_general
from movimientos.exceptions import DemoBloqueado, QrGeneralNoDisponible


class GuardasL2Tests(TestCase):
    def setUp(self):
        self.comercio = crear_comercio_con_cuenta_activa()

    @override_settings(DEMO_MODE="true")
    def test_demo_bloquea_servicios_sin_llamar_al_puerto(self):
        puerto = Mock()
        with patch("movimientos.alta_qr_general.obtener_puerto") as obtener:
            with self.assertRaises(DemoBloqueado):
                alta_qr_general(self.comercio)
            obtener.assert_not_called()
        datos = dict(
            comercio=self.comercio,
            monto=Decimal("1.00"),
            concepto="venta",
            referencia="0",
            puerto=puerto,
            clave="demo",
        )
        with self.assertRaises(DemoBloqueado):
            crear_venta_qr(**datos)
        with self.assertRaises(DemoBloqueado):
            crear_venta_notificacion(**datos, telefono="1234567890")
        puerto.assert_not_called()
        self.assertEqual(puerto.method_calls, [])

    @override_settings(DEMO_MODE="false")
    def test_varias_cuentas_bloquean_qr_general_sin_red(self):
        crear_cuenta(self.comercio, predeterminada=False)
        with patch("movimientos.alta_qr_general.obtener_puerto") as obtener:
            with self.assertRaises(QrGeneralNoDisponible):
                alta_qr_general(self.comercio)
            obtener.assert_not_called()
