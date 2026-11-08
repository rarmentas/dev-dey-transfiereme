"""El cobro de producción abona a la cuenta del comercio. Sin red."""

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from ambito.models import Comercio, Membresia
from pey.desarrollo import AdaptadorDesarrollo
from pey.produccion import AdaptadorProduccion
from ventas.servicio import CuentaNoActive, crear_venta_notificacion, crear_venta_qr

_CUENTA = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
_LLAVE = "llave-de-prueba"


def _transporte_qr(llamadas: list):
    def transporte(metodo, url, headers, cuerpo, timeout):
        llamadas.append(cuerpo)
        return 201, b'{"id":"qr-cuenta","qrString":"codi-qr"}'

    return transporte


def _transporte_pn(llamadas: list):
    def transporte(metodo, url, headers, cuerpo, timeout):
        llamadas.append(cuerpo)
        return 200, b'{"transactionId":"tx-cuenta","codiId":"12345678901234567890"}'

    return transporte


@override_settings(PEY_API_KEY=_LLAVE, PEY_BASE_URL="https://api.pey.mx")
class CobroALaCuentaDelComercioTests(TestCase):
    def setUp(self) -> None:
        self.comercio = Comercio.objects.create(
            nombre="Con cuenta",
            pey_codi_status=Comercio.PeyCodiStatus.ACTIVE,
            pey_bank_account_id=_CUENTA,
        )
        self.usuario = User.objects.create_user(username="cuenta", password="pass")
        Membresia.objects.create(usuario=self.usuario, comercio=self.comercio)

    def test_qr_de_produccion_envia_bank_account_id(self) -> None:
        llamadas: list[bytes] = []
        puerto = AdaptadorProduccion(transporte=_transporte_qr(llamadas))
        with patch("urllib.request.urlopen", side_effect=AssertionError("red")):
            crear_venta_qr(
                comercio=self.comercio,
                monto=Decimal("0.01"),
                concepto="Tacos",
                referencia="",
                puerto=puerto,
            )
        self.assertEqual(len(llamadas), 1)
        self.assertIn(b'"bankAccountId": "01ARZ3NDEKTSV4RRFFQ69G5FAV"', llamadas[0])

    def test_notificacion_de_produccion_envia_bank_account_id(self) -> None:
        llamadas: list[bytes] = []
        puerto = AdaptadorProduccion(transporte=_transporte_pn(llamadas))
        with patch("urllib.request.urlopen", side_effect=AssertionError("red")):
            crear_venta_notificacion(
                comercio=self.comercio,
                monto=Decimal("0.01"),
                telefono="5512345678",
                concepto="Aviso",
                referencia="",
                puerto=puerto,
            )
        self.assertEqual(len(llamadas), 1)
        self.assertIn(b'"bankAccountId": "01ARZ3NDEKTSV4RRFFQ69G5FAV"', llamadas[0])

    def test_produccion_sin_id_rechaza_sin_llamar(self) -> None:
        self.comercio.pey_bank_account_id = ""
        self.comercio.save(update_fields=["pey_bank_account_id"])
        llamadas: list[bytes] = []
        puerto = AdaptadorProduccion(transporte=_transporte_qr(llamadas))
        with patch("urllib.request.urlopen", side_effect=AssertionError("red")):
            with self.assertRaises(CuentaNoActive):
                crear_venta_qr(
                    comercio=self.comercio,
                    monto=Decimal("0.01"),
                    concepto="Tacos",
                    referencia="",
                    puerto=puerto,
                )
            with self.assertRaises(CuentaNoActive):
                crear_venta_notificacion(
                    comercio=self.comercio,
                    monto=Decimal("0.01"),
                    telefono="5512345678",
                    concepto="Aviso",
                    referencia="",
                    puerto=AdaptadorProduccion(transporte=_transporte_pn(llamadas)),
                )
        self.assertEqual(llamadas, [])

    def test_desarrollo_no_exige_la_cuenta(self) -> None:
        self.comercio.pey_bank_account_id = ""
        self.comercio.semilla_active_dev = True
        self.comercio.save(
            update_fields=["pey_bank_account_id", "semilla_active_dev"]
        )
        with patch("urllib.request.urlopen", side_effect=AssertionError("red")):
            venta = crear_venta_qr(
                comercio=self.comercio,
                monto=Decimal("0.01"),
                concepto="Tacos",
                referencia="",
                puerto=AdaptadorDesarrollo(),
            )
        self.assertTrue(venta.qr_string.startswith("cody-dev://qr/"))
