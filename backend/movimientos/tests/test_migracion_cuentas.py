"""Backfill de cobros desde el esquema real de MR-1."""

from ambito.tests.soporte import clabe_valida
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class MigracionCobroCuentaTests(TransactionTestCase):
    anterior = [
        ("ambito", "0005_comercio_secuencia_evento"),
        ("movimientos", "0005_cobro_pey_bank_account_id"),
        ("webhooks", "0002_alter_avisorecibido_resultado"),
        ("pedidos", "0001_initial"),
        ("canales", "0001_initial"),
    ]

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        executor.migrate(self.anterior)
        self.apps = executor.loader.project_state(self.anterior).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_sin_snapshot_unico_y_ambiguo(self):
        Comercio = self.apps.get_model("ambito", "Comercio")
        Cobro = self.apps.get_model("movimientos", "Cobro")
        comercio = Comercio.objects.create(nombre="Histórico")
        ids = ("01ARZ3NDEKTSV4RRFFQ69G5FAV", "01ARZ3NDEKTSV4RRFFQ69G5FAW")
        cobros = []
        for n, ident in enumerate(("", ids[0], ids[1])):
            cobros.append(
                Cobro.objects.create(
                    comercio_id=comercio.pk,
                    canal="qr_venta",
                    monto="1.00",
                    concepto="Histórico",
                    pey_qr_id=f"qr-{n}",
                    qr_string="qr",
                    pey_bank_account_id=ident,
                ).pk
            )
        objetivo = [
            ("ambito", "0007_cuentas_backfill"),
            ("movimientos", "0006_cobro_cuenta"),
        ]
        executor = MigrationExecutor(connection)
        executor.migrate(objetivo)
        apps = executor.loader.project_state(objetivo).apps
        Cuenta = apps.get_model("ambito", "CuentaCobro")
        unica = Cuenta.objects.create(
            comercio_id=comercio.pk, clabe=clabe_valida(1), pey_bank_account_id=ids[0]
        )
        Cuenta.objects.create(
            comercio_id=comercio.pk, clabe=clabe_valida(2), pey_bank_account_id=ids[1]
        )
        duplicada = Cuenta.objects.create(
            comercio_id=comercio.pk, clabe=clabe_valida(3), pey_bank_account_id=ids[1]
        )
        executor = MigrationExecutor(connection)
        executor.migrate([("movimientos", "0007_cobro_cuenta_backfill")])
        apps = executor.loader.project_state(
            [("movimientos", "0007_cobro_cuenta_backfill")]
        ).apps
        Cobro = apps.get_model("movimientos", "Cobro")
        self.assertIsNone(Cobro.objects.get(pk=cobros[0]).cuenta_id)
        self.assertEqual(Cobro.objects.get(pk=cobros[1]).cuenta_id, unica.pk)
        self.assertIsNone(Cobro.objects.get(pk=cobros[2]).cuenta_id)
        self.assertEqual(Cobro.objects.get(pk=cobros[2]).pey_bank_account_id, ids[1])
        Cuenta.objects.filter(pk=duplicada.pk).delete()
