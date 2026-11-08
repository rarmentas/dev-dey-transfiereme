"""El QR general de producción abona a la cuenta del comercio. Sin red."""

from unittest.mock import patch

from django.test import TestCase, override_settings

from ambito.exceptions import CuentaNoActiveError
from ambito.models import Comercio
from movimientos.alta_qr_general import alta_qr_general
from pey.desarrollo import AdaptadorDesarrollo
from pey.produccion import AdaptadorProduccion

_CUENTA = "01ARZ3NDEKTSV4RRFFQ69G5FAV"


@override_settings(PEY_API_KEY="llave-de-prueba", PEY_BASE_URL="https://api.pey.mx")
class AltaQrGeneralCuentaTests(TestCase):
    def _comercio(self, cuenta: str) -> Comercio:
        return Comercio.objects.create(
            nombre="QR",
            pey_codi_status=Comercio.PeyCodiStatus.ACTIVE,
            pey_bank_account_id=cuenta,
        )

    def test_produccion_envia_bank_account_id(self) -> None:
        llamadas: list[bytes] = []

        def transporte(metodo, url, headers, cuerpo, timeout):
            llamadas.append(cuerpo)
            return 201, b'{"id":"qr-general","qrString":"codi-general"}'

        puerto = AdaptadorProduccion(transporte=transporte)
        with patch("urllib.request.urlopen", side_effect=AssertionError("red")):
            with patch("movimientos.alta_qr_general.obtener_puerto", return_value=puerto):
                resultado = alta_qr_general(self._comercio(_CUENTA))
        self.assertTrue(resultado.creado)
        self.assertEqual(len(llamadas), 1)
        self.assertIn(b'"bankAccountId": "01ARZ3NDEKTSV4RRFFQ69G5FAV"', llamadas[0])

    def test_produccion_sin_id_rechaza_sin_llamar(self) -> None:
        llamadas: list[bytes] = []

        def transporte(metodo, url, headers, cuerpo, timeout):
            llamadas.append(cuerpo)
            return 201, b'{"id":"no","qrString":"no"}'

        puerto = AdaptadorProduccion(transporte=transporte)
        with patch("urllib.request.urlopen", side_effect=AssertionError("red")):
            with patch("movimientos.alta_qr_general.obtener_puerto", return_value=puerto):
                with self.assertRaises(CuentaNoActiveError):
                    alta_qr_general(self._comercio(""))
        self.assertEqual(llamadas, [])

    def test_desarrollo_no_exige_la_cuenta(self) -> None:
        with patch("urllib.request.urlopen", side_effect=AssertionError("red")):
            with patch(
                "movimientos.alta_qr_general.obtener_puerto",
                return_value=AdaptadorDesarrollo(),
            ):
                resultado = alta_qr_general(self._comercio(""))
        self.assertTrue(resultado.creado)
        self.assertTrue(resultado.cobro.qr_string.startswith("cody-dev://qr/"))
