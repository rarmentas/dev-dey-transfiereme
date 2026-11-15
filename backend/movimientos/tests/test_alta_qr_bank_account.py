"""El QR general de producción abona a la cuenta del comercio. Sin red."""

from unittest.mock import patch

from django.test import TestCase, override_settings

from ambito.cuentas_servicio import elegir_default
from ambito.exceptions import CuentaNoActiveError
from ambito.models import Comercio
from ambito.tests.soporte import crear_cuenta
from movimientos.alta_qr_general import alta_qr_general
from movimientos.exceptions import QrGeneralNoDisponible
from movimientos.models import Cobro, Movimiento
from pey.desarrollo import AdaptadorDesarrollo
from pey.produccion import AdaptadorProduccion

_CUENTA = "01ARZ3NDEKTSV4RRFFQ69G5FAV"


@override_settings(PEY_API_KEY="llave-de-prueba", PEY_BASE_URL="https://api.pey.mx")
class AltaQrGeneralCuentaTests(TestCase):
    def _comercio(self, cuenta: str) -> Comercio:
        comercio = Comercio.objects.create(nombre="QR")
        if cuenta:
            destino = crear_cuenta(comercio)
            destino.pey_bank_account_id = cuenta
            destino.save(update_fields=["pey_bank_account_id"])
        return comercio


    def test_produccion_envia_bank_account_id(self) -> None:
        llamadas: list[bytes] = []

        def transporte(metodo, url, headers, cuerpo, timeout):
            llamadas.append(cuerpo)
            return 201, b'{"id":"qr-general","qrString":"codi-general"}'

        puerto = AdaptadorProduccion(transporte=transporte)
        with patch("urllib.request.urlopen", side_effect=AssertionError("red")):
            with patch(
                "movimientos.alta_qr_general.obtener_puerto", return_value=puerto
            ):
                resultado = alta_qr_general(self._comercio(_CUENTA))
        self.assertTrue(resultado.creado)
        self.assertEqual(len(llamadas), 1)
        self.assertIn(b'"bankAccountId": "01ARZ3NDEKTSV4RRFFQ69G5FAV"', llamadas[0])
        self.assertEqual(resultado.cobro.pey_bank_account_id, _CUENTA)
        self.assertEqual(resultado.cobro.cuenta.pey_bank_account_id, _CUENTA)

    def _alta_con_cambio(self, ident, cambio, error) -> list[bytes]:
        comercio = self._comercio(ident)
        llamadas: list[bytes] = []

        def transporte(metodo, url, headers, cuerpo, timeout):
            llamadas.append(cuerpo)
            cambio(comercio)
            return 201, b'{"id":"qr-general","qrString":"codi-general"}'

        puerto = AdaptadorProduccion(transporte=transporte)
        with patch("movimientos.alta_qr_general.obtener_puerto", return_value=puerto):
            with self.assertRaises(error):
                alta_qr_general(comercio)
        self.assertFalse(Cobro.objects.filter(comercio=comercio).exists())
        return llamadas

    def test_cambio_de_cuentas_durante_el_alta_no_publica_qr(self) -> None:
        def agregar(comercio):
            crear_cuenta(comercio, predeterminada=False)

        def agregar_y_elegir(comercio):
            nueva = crear_cuenta(comercio, predeterminada=False)
            elegir_default(comercio, nueva, nueva.version)

        def desactivar(comercio):
            comercio.cuentas.update(codi_status="pending")

        for ident, cambio, error in (
            ("01ARZ3NDEKTSV4RRFFQ69G5FA1", agregar, QrGeneralNoDisponible),
            ("01ARZ3NDEKTSV4RRFFQ69G5FA2", agregar_y_elegir, QrGeneralNoDisponible),
            ("01ARZ3NDEKTSV4RRFFQ69G5FA3", desactivar, CuentaNoActiveError),
        ):
            with self.subTest(cambio=cambio.__name__):
                llamadas = self._alta_con_cambio(ident, cambio, error)
                self.assertEqual(len(llamadas), 1)
                self.assertIn(ident.encode(), llamadas[0])

    def test_produccion_sin_id_rechaza_sin_llamar(self) -> None:
        llamadas: list[bytes] = []

        def transporte(metodo, url, headers, cuerpo, timeout):
            llamadas.append(cuerpo)
            return 201, b'{"id":"no","qrString":"no"}'

        puerto = AdaptadorProduccion(transporte=transporte)
        with patch("urllib.request.urlopen", side_effect=AssertionError("red")):
            with patch(
                "movimientos.alta_qr_general.obtener_puerto", return_value=puerto
            ):
                with self.assertRaises(CuentaNoActiveError):
                    alta_qr_general(self._comercio(""))
        self.assertEqual(llamadas, [])

    def test_desarrollo_usa_default_sin_enviar_id(self) -> None:
        with patch("urllib.request.urlopen", side_effect=AssertionError("red")):
            with patch(
                "movimientos.alta_qr_general.obtener_puerto",
                return_value=AdaptadorDesarrollo(),
            ):
                resultado = alta_qr_general(self._comercio(_CUENTA))
        self.assertTrue(resultado.creado)
        self.assertTrue(resultado.cobro.qr_string.startswith("cody-dev://qr/"))
        self.assertEqual(resultado.cobro.pey_bank_account_id, "")

    def test_qr_previo_sin_id_no_se_redirige(self) -> None:
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
        puerto = AdaptadorProduccion(transporte=lambda *args: self.fail("red"))
        with patch("movimientos.alta_qr_general.obtener_puerto", return_value=puerto):
            with self.assertRaises(QrGeneralNoDisponible):
                alta_qr_general(comercio)
        viejo.refresh_from_db()
        self.assertEqual(viejo.pey_qr_id, "qr-viejo")
        self.assertEqual(viejo.qr_string, "viejo")
        self.assertEqual(viejo.pey_bank_account_id, "")

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
            with patch(
                "movimientos.alta_qr_general.obtener_puerto", return_value=puerto
            ):
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
            with patch(
                "movimientos.alta_qr_general.obtener_puerto", return_value=puerto
            ):
                with self.assertRaises(CuentaNoActiveError):
                    alta_qr_general(comercio)
        viejo.refresh_from_db()
        self.assertEqual(viejo.qr_string, "sigue")
        self.assertEqual(llamadas, [])
