"""El QR general de producción abona a la cuenta del comercio. Sin red."""

from unittest.mock import patch

from django.test import TestCase, override_settings

from ambito.exceptions import CuentaNoActiveError
from ambito.models import Comercio
from movimientos.alta_qr_general import alta_qr_general
from movimientos.models import Cobro, Movimiento
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
        self.assertEqual(resultado.cobro.pey_bank_account_id, _CUENTA)

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
        self.assertEqual(resultado.cobro.pey_bank_account_id, "")

    def test_qr_previo_sin_id_se_regenera_con_la_cuenta(self) -> None:
        comercio = self._comercio(_CUENTA)
        viejo = Cobro.objects.create(
            comercio=comercio,
            canal=Movimiento.Canal.QR_GENERAL,
            monto=0,
            concepto="Transferencia",
            pey_qr_id="qr-viejo",
            qr_string="viejo",
            pey_bank_account_id="",
        )
        llamadas: list[bytes] = []

        def transporte(metodo, url, headers, cuerpo, timeout):
            llamadas.append(cuerpo)
            return 201, b'{"id":"qr-nuevo","qrString":"nuevo"}'

        puerto = AdaptadorProduccion(transporte=transporte)
        with patch("urllib.request.urlopen", side_effect=AssertionError("red")):
            with patch("movimientos.alta_qr_general.obtener_puerto", return_value=puerto):
                with self.assertLogs("movimientos.alta_qr_general", level="WARNING") as logs:
                    resultado = alta_qr_general(comercio)
        viejo.refresh_from_db()
        self.assertEqual(resultado.cobro.pk, viejo.pk)
        self.assertFalse(resultado.creado)
        self.assertEqual(viejo.pey_qr_id, "qr-nuevo")
        self.assertEqual(viejo.qr_string, "nuevo")
        self.assertEqual(viejo.pey_bank_account_id, _CUENTA)
        self.assertIsNone(viejo.pey_transaction_id)
        self.assertEqual(len(llamadas), 1)
        self.assertIn(b'"bankAccountId": "01ARZ3NDEKTSV4RRFFQ69G5FAV"', llamadas[0])
        self.assertIn("QR general regenerado", " ".join(logs.output))
        self.assertIn(str(viejo.pk), " ".join(logs.output))

    def test_qr_previo_con_la_misma_cuenta_no_llama_a_pey(self) -> None:
        comercio = self._comercio(_CUENTA)
        Cobro.objects.create(
            comercio=comercio,
            canal=Movimiento.Canal.QR_GENERAL,
            monto=0,
            concepto="Transferencia",
            pey_qr_id="qr-ok",
            qr_string="igual",
            pey_bank_account_id=_CUENTA,
        )
        llamadas: list[bytes] = []

        def transporte(metodo, url, headers, cuerpo, timeout):
            llamadas.append(cuerpo)
            return 201, b'{"id":"no","qrString":"no"}'

        puerto = AdaptadorProduccion(transporte=transporte)
        with patch("urllib.request.urlopen", side_effect=AssertionError("red")):
            with patch("movimientos.alta_qr_general.obtener_puerto", return_value=puerto):
                resultado = alta_qr_general(comercio)
        self.assertFalse(resultado.creado)
        self.assertEqual(resultado.cobro.qr_string, "igual")
        self.assertEqual(resultado.cobro.pey_qr_id, "qr-ok")
        self.assertEqual(llamadas, [])

    def test_comercio_sin_id_y_qr_previo_rechaza_sin_llamar(self) -> None:
        comercio = self._comercio("")
        viejo = Cobro.objects.create(
            comercio=comercio,
            canal=Movimiento.Canal.QR_GENERAL,
            monto=0,
            concepto="Transferencia",
            pey_qr_id="qr-viejo-2",
            qr_string="sigue",
        )
        llamadas: list[bytes] = []

        def transporte(metodo, url, headers, cuerpo, timeout):
            llamadas.append(cuerpo)
            return 201, b'{"id":"no","qrString":"no"}'

        puerto = AdaptadorProduccion(transporte=transporte)
        with patch("urllib.request.urlopen", side_effect=AssertionError("red")):
            with patch("movimientos.alta_qr_general.obtener_puerto", return_value=puerto):
                with self.assertRaises(CuentaNoActiveError):
                    alta_qr_general(comercio)
        viejo.refresh_from_db()
        self.assertEqual(viejo.qr_string, "sigue")
        self.assertEqual(llamadas, [])
