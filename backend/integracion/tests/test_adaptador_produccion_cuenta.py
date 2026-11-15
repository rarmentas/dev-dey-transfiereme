"""Consulta de cuenta en producción. consultar_cuenta está parcheado: no hay red."""

from unittest.mock import patch

from django.test import TestCase

from ambito.models import CuentaCobro
from integracion.pey.adaptador_produccion import AdaptadorProduccionPeyCuenta
from integracion.pey.puerto import CODI_STATUS_ACTIVE, CODI_STATUS_PENDING
from pey.cuentas import CuentaPey

_ID = "01J9ZQ4C8X7Y6W5V4T3S2R1Q0P"
_CLABE = "012180015826225713"
_OTRA = "032180000118359719"


class AdaptadorProduccionCuentaTests(TestCase):
    def setUp(self) -> None:
        self.adaptador = AdaptadorProduccionPeyCuenta()
        self.red = patch("urllib.request.urlopen", side_effect=AssertionError("red"))
        self.red.start()
        self.addCleanup(self.red.stop)

    def test_sin_id_es_pending_sin_transporte(self) -> None:
        cuenta = CuentaCobro(
            pey_bank_account_id="",
        )
        with patch(
            "integracion.pey.adaptador_produccion.consultar_cuenta",
            side_effect=AssertionError("no debe consultar"),
        ):
            resultado = self.adaptador.consultar_cuenta(cuenta)
        self.assertEqual(resultado.codi_status, CODI_STATUS_PENDING)
        self.assertEqual(resultado.bank_account_id, "")

    def test_active_de_pey_es_active(self) -> None:
        cuenta = CuentaCobro(
            pey_bank_account_id=_ID,
            clabe=_CLABE,
        )
        with patch(
            "integracion.pey.adaptador_produccion.consultar_cuenta",
            return_value=CuentaPey(id=_ID, codi_status="ACTIVE", clabe=_CLABE),
        ) as consulta:
            resultado = self.adaptador.consultar_cuenta(cuenta)
        consulta.assert_called_once_with(_ID)
        self.assertEqual(resultado.codi_status, CODI_STATUS_ACTIVE)
        self.assertEqual(resultado.bank_account_id, _ID)

    def test_otros_estados_siguen_pending_y_conservan_el_id(self) -> None:
        for estado in ("PENDING", "PROCESSING", "ERROR"):
            with self.subTest(estado=estado):
                cuenta = CuentaCobro(
                    pey_bank_account_id=_ID,
                        )
                with patch(
                    "integracion.pey.adaptador_produccion.consultar_cuenta",
                    return_value=CuentaPey(id=_ID, codi_status=estado),
                ):
                    resultado = self.adaptador.consultar_cuenta(cuenta)
                self.assertEqual(resultado.codi_status, CODI_STATUS_PENDING)
                self.assertEqual(resultado.bank_account_id, _ID)

    def test_clabe_distinta_no_es_active_y_avisa_con_cuatro_digitos(self) -> None:
        cuenta = CuentaCobro(
            pey_bank_account_id=_ID,
            clabe=_CLABE,
        )
        with self.assertNoLogs("integracion.pey.adaptador_produccion", level="WARNING"):
            with patch(
                "integracion.pey.adaptador_produccion.consultar_cuenta",
                return_value=CuentaPey(id=_ID, codi_status="ACTIVE", clabe=_OTRA),
            ):
                resultado = self.adaptador.consultar_cuenta(cuenta)
        self.assertEqual(resultado.codi_status, CODI_STATUS_PENDING)
        self.assertEqual(resultado.bank_account_id, _ID)

    def test_error_pey_no_se_convierte_en_active(self) -> None:
        from pey.tipos import ErrorPey

        cuenta = CuentaCobro(
            pey_bank_account_id=_ID,
        )
        with patch(
            "integracion.pey.adaptador_produccion.consultar_cuenta",
            side_effect=ErrorPey("NO_DISPONIBLE", "caído", "req-1"),
        ):
            with self.assertRaises(ErrorPey) as ctx:
                self.adaptador.consultar_cuenta(cuenta)
        self.assertEqual(ctx.exception.tipo, "NO_DISPONIBLE")
        self.assertNotEqual(getattr(ctx.exception, "tipo", ""), "ACTIVE")
