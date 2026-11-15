from decimal import Decimal

from django.test import SimpleTestCase

from pedidos.contratos.calculo import (
    importe_efectivo,
    subtotal_centavos,
    total_centavos,
)
from pedidos.contratos.validacion import ErrorContrato


class CalculoTests(SimpleTestCase):
    def test_redondeo_half_up(self):
        self.assertEqual(subtotal_centavos(Decimal("0.333"), 750), 250)
        self.assertEqual(subtotal_centavos(Decimal("0.5"), 1), 1)

    def test_subtotal_cero_y_escala_excesiva(self):
        for cantidad in (Decimal("0.001"), Decimal("1.0001")):
            with self.subTest(cantidad=cantidad), self.assertRaises(ErrorContrato):
                subtotal_centavos(cantidad, 1)

    def test_total_y_tope(self):
        self.assertEqual(total_centavos([1000, 1500]), 2500)
        self.assertEqual(total_centavos([100_000_000]), 100_000_000)
        for valores in ([], [100_000_001], [0]):
            with self.subTest(valores=valores), self.assertRaises(ErrorContrato):
                total_centavos(valores)

    def test_demo_no_altera_total_comercial(self):
        self.assertEqual(importe_efectivo(2500, True), 1)
        self.assertEqual(importe_efectivo(2500, False), 2500)
