from unittest.mock import patch

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from ambito.tests.soporte import clabe_valida


class MigracionCuentasTests(TransactionTestCase):
    migrate_from = [
        ("ambito", "0005_comercio_secuencia_evento"),
        ("movimientos", "0005_cobro_pey_bank_account_id"),
        ("webhooks", "0002_alter_avisorecibido_resultado"),
        ("pedidos", "0001_initial"),
        ("canales", "0001_initial"),
    ]

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        self.apps = executor.loader.project_state(self.migrate_from).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_backfill_desde_mr1_sin_red(self):
        Comercio = self.apps.get_model("ambito", "Comercio")
        id_activo = "01J9ZQ4C8X7Y6W5V4T3S2R1Q0P"
        activa = Comercio.objects.create(
            nombre="Activa",
            clabe=clabe_valida(1),
            pey_bank_account_id=id_activo,
            pey_codi_status="active",
        )
        pendiente = Comercio.objects.create(
            nombre="Pendiente", clabe=clabe_valida(2), pey_codi_status="pending"
        )
        sin_id = Comercio.objects.create(
            nombre="Sin ID", clabe=clabe_valida(3), pey_codi_status="active"
        )
        sin_clabe = Comercio.objects.create(
            nombre="Sin CLABE",
            pey_bank_account_id="01J9ZQ4C8X7Y6W5V4T3S2R1Q0Q",
            pey_codi_status="active",
        )
        Usuario = self.apps.get_model("auth", "User")
        Membresia = self.apps.get_model("ambito", "Membresia")
        usuario = Usuario.objects.create(username="legado")
        Membresia.objects.create(usuario_id=usuario.pk, comercio_id=activa.pk)
        Cobro = self.apps.get_model("movimientos", "Cobro")
        cobro = Cobro.objects.create(
            comercio_id=activa.pk,
            canal="qr_venta",
            monto="1.00",
            concepto="Histórico",
            pey_qr_id="qr-historico",
            pey_bank_account_id="",
        )
        with patch("socket.socket", side_effect=AssertionError("red prohibida")):
            executor = MigrationExecutor(connection)
            executor.migrate([("ambito", "0008_cuentas_cutover")])
        apps = executor.loader.project_state([("ambito", "0008_cuentas_cutover")]).apps
        Comercio = apps.get_model("ambito", "Comercio")
        Cuenta = apps.get_model("ambito", "CuentaCobro")
        activa = Comercio.objects.get(pk=activa.pk)
        self.assertEqual(activa.cuenta_por_defecto.clabe, clabe_valida(1))
        self.assertEqual(activa.cuenta_por_defecto.codi_status, "active")
        self.assertIsNone(Comercio.objects.get(pk=pendiente.pk).cuenta_por_defecto_id)
        self.assertEqual(
            Cuenta.objects.get(comercio_id=sin_id.pk).anomalia, "ACTIVE_SIN_ID"
        )
        self.assertEqual(
            Cuenta.objects.get(comercio_id=sin_id.pk).codi_status, "pending"
        )
        self.assertIsNone(Comercio.objects.get(pk=sin_id.pk).cuenta_por_defecto_id)
        self.assertEqual(
            Cuenta.objects.get(comercio_id=pendiente.pk).codi_status, "pending"
        )
        self.assertFalse(Cuenta.objects.filter(comercio_id=sin_clabe.pk).exists())
        membresia = apps.get_model("ambito", "Membresia").objects.get(
            usuario_id=usuario.pk
        )
        self.assertFalse(membresia.es_dueno)
        self.assertEqual(Cobro.objects.get(pk=cobro.pk).pey_bank_account_id, "")
        cuenta_id = activa.cuenta_por_defecto_id
        executor = MigrationExecutor(connection)
        executor.migrate([("ambito", "0006_cuentas_expand")])
        executor = MigrationExecutor(connection)
        executor.migrate([("ambito", "0008_cuentas_cutover")])
        self.assertEqual(Cuenta.objects.filter(comercio_id=activa.pk).count(), 1)
        self.assertEqual(
            Comercio.objects.get(pk=activa.pk).cuenta_por_defecto_id, cuenta_id
        )
        self.assertEqual(Cobro.objects.get(pk=cobro.pk).pey_bank_account_id, "")

    def test_id_duplicado_aborta_antes_del_cutover(self):
        Comercio = self.apps.get_model("ambito", "Comercio")
        ident = "01J9ZQ4C8X7Y6W5V4T3S2R1Q0P"
        a = Comercio.objects.create(
            nombre="A", clabe=clabe_valida(1), pey_bank_account_id=ident
        )
        b = Comercio.objects.create(
            nombre="B", clabe=clabe_valida(2), pey_bank_account_id=ident
        )
        with self.assertRaises(RuntimeError) as error:
            MigrationExecutor(connection).migrate([("ambito", "0008_cuentas_cutover")])
        self.assertIn(str(a.pk), str(error.exception))
        self.assertIn(str(b.pk), str(error.exception))
        self.assertNotIn(ident, str(error.exception))
        self.assertNotIn(a.clabe, str(error.exception))
        self.assertFalse(
            MigrationExecutor(connection)
            .recorder.applied_migrations()
            .get(("ambito", "0008_cuentas_cutover"))
        )
        Comercio.objects.filter(pk=b.pk).update(pey_bank_account_id="")
