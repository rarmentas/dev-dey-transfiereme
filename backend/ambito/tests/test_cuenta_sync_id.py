"""Sincronizar conserva el identificador de la cuenta registrada."""

from unittest.mock import patch

from django.test import TestCase

from ambito.models import Comercio
from ambito.operaciones_cuenta import sincronizar
from ambito.tests.soporte import crear_cuenta
from pey.cuentas import CuentaPey
from pey.tipos import ErrorPey


class CuentaSyncIdTests(TestCase):
    def test_pending_de_produccion_conserva_el_id(self) -> None:
        comercio = Comercio.objects.create(nombre="En proceso")
        cuenta = crear_cuenta(comercio)
        identificador = cuenta.pey_bank_account_id
        with patch(
            "ambito.operaciones_cuenta.consultar_cuenta",
            return_value=CuentaPey(id=identificador, codi_status="PROCESSING"),
        ):
            sincronizar(cuenta)
        cuenta.refresh_from_db()
        self.assertEqual(cuenta.codi_status, "pending")
        self.assertEqual(cuenta.pey_bank_account_id, identificador)

    def test_cuenta_no_encontrada_conserva_el_id(self) -> None:
        cuenta = crear_cuenta(Comercio.objects.create(nombre="Local"))
        identificador = cuenta.pey_bank_account_id
        with patch(
            "ambito.operaciones_cuenta.consultar_cuenta",
            side_effect=ErrorPey("BANK_ACCOUNT_NOT_FOUND", "no encontrada"),
        ):
            sincronizar(cuenta)
        cuenta.refresh_from_db()
        self.assertEqual(cuenta.codi_status, "pending")
        self.assertEqual(cuenta.pey_bank_account_id, identificador)
