from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.db import close_old_connections, connections
from django.test import TransactionTestCase

from ambito.cuentas_servicio import elegir_default
from ambito.models import Comercio
from ambito.operaciones_cuenta import ErrorOperacion
from ambito.tests.soporte import crear_cuenta


class CuentasDefaultTests(TransactionTestCase):
    def test_ac1_13_default_solo_registrada_active_y_unica(self):
        comercio = Comercio.objects.create(nombre="A")
        anterior = crear_cuenta(comercio)
        pendiente = crear_cuenta(comercio, estado="pending", predeterminada=False)
        ajena = crear_cuenta(Comercio.objects.create(nombre="B"))
        for cuenta in (pendiente, ajena):
            with self.assertRaises(ErrorOperacion):
                elegir_default(comercio, cuenta, cuenta.version)
        comercio.refresh_from_db()
        self.assertEqual(comercio.cuenta_por_defecto_id, anterior.pk)
        pendiente.registro_estado = "sin_registro"
        pendiente.pey_bank_account_id = ""
        pendiente.save(update_fields=["registro_estado", "pey_bank_account_id"])
        with self.assertRaises(ErrorOperacion):
            elegir_default(comercio, pendiente, pendiente.version)
        comercio.refresh_from_db()
        self.assertEqual(comercio.cuenta_por_defecto_id, anterior.pk)

    def test_dos_defaults_concurrentes_dejan_uno(self):
        comercio = Comercio.objects.create(nombre="A")
        cuentas = [crear_cuenta(comercio, predeterminada=False) for _ in range(2)]
        barrera = Barrier(2)

        def elegir(cuenta):
            close_old_connections()
            try:
                barrera.wait()
                elegir_default(
                    Comercio.objects.get(pk=comercio.pk), cuenta, cuenta.version
                )
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            list(executor.map(elegir, cuentas))
        comercio.refresh_from_db()
        self.assertIn(comercio.cuenta_por_defecto_id, [c.pk for c in cuentas])
        self.assertEqual(
            comercio.cuentas.filter(pk=comercio.cuenta_por_defecto_id).count(), 1
        )
