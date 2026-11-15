"""Las cuentas no pueden registrar ni acreditar el destino demo."""

from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from ambito.cuenta import cuenta_apta
from ambito.models import Comercio, CuentaCobro
from ambito.operaciones_cuenta import ErrorOperacion, registrar, sincronizar
from ambito.tests.soporte import crear_cuenta
from pey.cuentas import CuentaPey

DESTINO = "01ARZ3NDEKTSV4RRFFQ69G5FAV"


@override_settings(DEMO_PEY_BANK_ACCOUNT_ID=DESTINO)
class ReservaDestinoDemoTests(TestCase):
    def cuenta(self, registro_estado):
        cuenta = crear_cuenta(
            Comercio.objects.create(nombre="B"), "pending", predeterminada=False
        )
        CuentaCobro.objects.filter(pk=cuenta.pk).update(
            pey_bank_account_id="", registro_estado=registro_estado
        )
        cuenta.refresh_from_db()
        return cuenta

    def test_registro_que_devuelve_el_destino_demo_queda_incierto(self):
        cuenta = self.cuenta("sin_registro")
        with (
            patch("ambito.operaciones_cuenta.exigir_modo_produccion"),
            patch(
                "ambito.operaciones_cuenta.registrar_cuenta",
                return_value=CuentaPey(DESTINO, "ACTIVE"),
            ),
            self.assertRaises(ErrorOperacion) as error,
        ):
            registrar(
                cuenta,
                nombre="Ana",
                entidad="PERSON",
                alias="",
                clave="k",
                version=cuenta.version,
            )
        self.assertEqual(error.exception.codigo, "PEY_INCIERTO")
        cuenta.refresh_from_db()
        self.assertEqual(
            (cuenta.registro_estado, cuenta.pey_bank_account_id, cuenta.codi_status),
            ("incierto", "", "pending"),
        )

    def test_enlace_del_destino_demo_se_rechaza_sin_consultar(self):
        cuenta = self.cuenta("incierto")
        with patch(
            "ambito.management.commands.enlazar_cuenta_pey.consultar_cuenta"
        ) as consulta:
            with self.assertRaises(CommandError):
                call_command(
                    "enlazar_cuenta_pey", cuenta=str(cuenta.pk), pey_id=DESTINO
                )
        consulta.assert_not_called()
        cuenta.refresh_from_db()
        self.assertEqual(cuenta.pey_bank_account_id, "")

    def test_sync_no_acredita_una_cuenta_con_el_destino_demo(self):
        cuenta = crear_cuenta(Comercio.objects.create(nombre="B"), "pending")
        CuentaCobro.objects.filter(pk=cuenta.pk).update(pey_bank_account_id=DESTINO)
        cuenta.refresh_from_db()
        with patch(
            "ambito.operaciones_cuenta.consultar_cuenta",
            return_value=CuentaPey(DESTINO, "ACTIVE", cuenta.clabe),
        ):
            sincronizar(cuenta)
        cuenta.refresh_from_db()
        self.assertEqual(
            (cuenta.codi_status, cuenta.anomalia), ("pending", "ID_RESERVADO_DEMO")
        )
        self.assertFalse(cuenta_apta(cuenta))
