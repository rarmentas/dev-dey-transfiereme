"""Consulta de cuenta en producción. consultar_cuenta está parcheado: no hay red."""

from unittest.mock import patch

from django.test import TestCase

from ambito.models import Comercio
from integracion.pey.adaptador_produccion import AdaptadorProduccionPeyCuenta
from integracion.pey.puerto import CODI_STATUS_ACTIVE, CODI_STATUS_PENDING
from pey.cuentas import CuentaPey

_ID = "01CUENTA0000000000000001"


class AdaptadorProduccionCuentaTests(TestCase):
    def setUp(self) -> None:
        self.adaptador = AdaptadorProduccionPeyCuenta()
        self.red = patch("urllib.request.urlopen", side_effect=AssertionError("red"))
        self.red.start()
        self.addCleanup(self.red.stop)

    def test_sin_id_es_pending_sin_transporte(self) -> None:
        comercio = Comercio(
            nombre="Sin registrar",
            semilla_active_dev=True,
            pey_bank_account_id="",
        )
        with patch(
            "integracion.pey.adaptador_produccion.consultar_cuenta",
            side_effect=AssertionError("no debe consultar"),
        ):
            resultado = self.adaptador.consultar_cuenta_por_clabe(comercio)
        self.assertEqual(resultado.codi_status, CODI_STATUS_PENDING)
        self.assertEqual(resultado.bank_account_id, "")

    def test_active_de_pey_es_active(self) -> None:
        comercio = Comercio(nombre="Lista", pey_bank_account_id=_ID, semilla_active_dev=False)
        with patch(
            "integracion.pey.adaptador_produccion.consultar_cuenta",
            return_value=CuentaPey(id=_ID, codi_status="ACTIVE"),
        ) as consulta:
            resultado = self.adaptador.consultar_cuenta_por_clabe(comercio)
        consulta.assert_called_once_with(_ID)
        self.assertEqual(resultado.codi_status, CODI_STATUS_ACTIVE)
        self.assertEqual(resultado.bank_account_id, _ID)

    def test_otros_estados_siguen_pending_y_conservan_el_id(self) -> None:
        for estado in ("PENDING", "PROCESSING", "ERROR"):
            with self.subTest(estado=estado):
                comercio = Comercio(
                    nombre=estado,
                    pey_bank_account_id=_ID,
                    semilla_active_dev=True,
                )
                with patch(
                    "integracion.pey.adaptador_produccion.consultar_cuenta",
                    return_value=CuentaPey(id=_ID, codi_status=estado),
                ):
                    resultado = self.adaptador.consultar_cuenta_por_clabe(comercio)
                self.assertEqual(resultado.codi_status, CODI_STATUS_PENDING)
                self.assertEqual(resultado.bank_account_id, _ID)

    def test_error_pey_no_se_convierte_en_active(self) -> None:
        from pey.tipos import ErrorPey

        comercio = Comercio(
            nombre="Fallo",
            pey_bank_account_id=_ID,
            semilla_active_dev=True,
        )
        with patch(
            "integracion.pey.adaptador_produccion.consultar_cuenta",
            side_effect=ErrorPey("NO_DISPONIBLE", "caído", "req-1"),
        ):
            with self.assertRaises(ErrorPey) as ctx:
                self.adaptador.consultar_cuenta_por_clabe(comercio)
        self.assertEqual(ctx.exception.tipo, "NO_DISPONIBLE")
        self.assertNotEqual(getattr(ctx.exception, "tipo", ""), "ACTIVE")
