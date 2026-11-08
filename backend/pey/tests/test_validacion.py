from decimal import Decimal

from django.test import SimpleTestCase

from pey.tipos import ParametroInvalido
from pey.validacion import validar_notificacion, validar_qr

_RECHAZADOS = (
    Decimal("-0.00"),
    Decimal("-0"),
    Decimal("0.005"),
    Decimal("10.500"),
    Decimal("1e27"),
    Decimal("12345678901234567890123456.789"),
    Decimal("NaN"),
    Decimal("Infinity"),
)


class MontosTests(SimpleTestCase):
    def test_rechaza_montos_que_no_son_centavos(self) -> None:
        for monto in _RECHAZADOS:
            with self.assertRaises(ParametroInvalido):
                validar_qr(monto=monto, concepto="Tacos", expiracion_s=0, num_ref="0")
            with self.assertRaises(ParametroInvalido):
                validar_notificacion(
                    monto=monto,
                    telefono="5512345678",
                    concepto="Tacos",
                    expiracion_s=360,
                    num_ref="0",
                )

    def test_uno_diez_es_valido_y_queda_en_centavos(self) -> None:
        qr = validar_qr(
            monto=Decimal("1.10"),
            concepto="   ",
            expiracion_s=0,
            num_ref="0",
        )
        aviso = validar_notificacion(
            monto=Decimal("1.10"),
            telefono="5512345678",
            concepto=" \t ",
            expiracion_s=360,
            num_ref="0",
        )
        self.assertEqual(qr.monto, Decimal("1.10"))
        self.assertEqual(qr.monto.as_tuple().exponent, -2)
        self.assertEqual(format(qr.monto, "f"), "1.10")
        self.assertEqual(aviso.monto, Decimal("1.10"))
        self.assertEqual(qr.concepto, "Transferencia")
        self.assertEqual(aviso.concepto, "Transferencia")

    def test_el_qr_acepta_hasta_decimal_12_2_y_la_notificacion_no(self) -> None:
        qr = validar_qr(
            monto=Decimal("9999999999.99"),
            concepto="Tacos",
            expiracion_s=0,
            num_ref="0",
        )
        self.assertEqual(format(qr.monto, "f"), "9999999999.99")
        with self.assertRaises(ParametroInvalido):
            validar_qr(
                monto=Decimal("10000000000"),
                concepto="Tacos",
                expiracion_s=0,
                num_ref="0",
            )
        with self.assertRaises(ParametroInvalido):
            validar_notificacion(
                monto=Decimal("9999999999.99"),
                telefono="5512345678",
                concepto="Tacos",
                expiracion_s=360,
                num_ref="0",
            )
