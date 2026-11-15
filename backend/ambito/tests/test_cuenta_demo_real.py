"""El uso demo no impide registrar, enlazar ni sincronizar cuentas reales."""

from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings

from ambito.cuenta import cuenta_apta
from ambito.models import Comercio
from ambito.operaciones_cuenta import registrar, sincronizar
from ambito.tests.soporte import crear_cuenta
from pedidos.models import IntentoCobro
from pey.cuentas import CuentaPey

DESTINO = "01ARZ3NDEKTSV4RRFFQ69G5FAV"


@override_settings(DEMO_PEY_BANK_ACCOUNT_ID=DESTINO)
class CuentaDemoRealTests(TestCase):
    def setUp(self):
        comercio = Comercio.objects.create(nombre="Demo", es_demo=True)
        self.cuenta = crear_cuenta(comercio, "pending")
        self.cuenta.pey_bank_account_id = ""
        self.cuenta.registro_estado = "sin_registro"
        self.cuenta.save(update_fields=["pey_bank_account_id", "registro_estado"])
        IntentoCobro.objects.create(
            comercio=comercio,
            origen="legado",
            canal="qr_venta",
            estado="descartado",
            demo_mode=True,
            politica_cobro_version="demo-1",
            importe_efectivo_centavos=1,
            pey_bank_account_id=DESTINO,
            concepto="histórico",
            expiracion_s=600,
            clave_legado="demo-historico",
        )

    def test_registro_acepta_id_usado_en_demo(self):
        with (
            patch("ambito.operaciones_cuenta.exigir_modo_produccion"),
            patch(
                "ambito.operaciones_cuenta.registrar_cuenta",
                return_value=CuentaPey(DESTINO, "ACTIVE"),
            ),
        ):
            cuenta, _ = registrar(
                self.cuenta,
                nombre="Ana",
                entidad="PERSON",
                alias="",
                clave="registro",
                version=self.cuenta.version,
            )
        self.assertEqual(cuenta.pey_bank_account_id, DESTINO)
        self.assertTrue(cuenta_apta(cuenta))

    def test_enlace_acepta_id_usado_en_demo(self):
        self.cuenta.registro_estado = "incierto"
        self.cuenta.save(update_fields=["registro_estado"])
        with patch(
            "ambito.management.commands.enlazar_cuenta_pey.consultar_cuenta",
            return_value=CuentaPey(DESTINO, "ACTIVE", self.cuenta.clabe),
        ):
            call_command(
                "enlazar_cuenta_pey",
                cuenta=str(self.cuenta.pk),
                pey_id=DESTINO,
                stdout=StringIO(),
            )
        self.cuenta.refresh_from_db()
        self.assertEqual(self.cuenta.pey_bank_account_id, DESTINO)
        self.assertTrue(cuenta_apta(self.cuenta))

    def test_sync_acredita_cuenta_usada_en_demo(self):
        self.cuenta.registro_estado = "registrado"
        self.cuenta.pey_bank_account_id = DESTINO
        self.cuenta.save(update_fields=["registro_estado", "pey_bank_account_id"])
        with patch(
            "ambito.operaciones_cuenta.consultar_cuenta",
            return_value=CuentaPey(DESTINO, "ACTIVE", self.cuenta.clabe),
        ):
            sincronizar(self.cuenta)
        self.cuenta.refresh_from_db()
        self.assertTrue(cuenta_apta(self.cuenta))
        self.assertEqual(self.cuenta.anomalia, "")
