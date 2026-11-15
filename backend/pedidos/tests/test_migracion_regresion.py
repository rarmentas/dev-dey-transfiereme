from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class MigracionRegresionTests(TransactionTestCase):
    def test_conserva_comercio_cobro_y_movimiento_previos(self):
        anteriores = [
            ("ambito", "0005_comercio_secuencia_evento"),
            ("movimientos", "0005_cobro_pey_bank_account_id"),
            ("pedidos", "0001_initial"),
            ("webhooks", "0002_alter_avisorecibido_resultado"),
            ("canales", "0001_initial"),
        ]
        ejecutor = MigrationExecutor(connection)
        try:
            ejecutor.migrate(anteriores)
            apps = ejecutor.loader.project_state(anteriores).apps
            comercio = apps.get_model("ambito", "Comercio").objects.create(
                nombre="Existente", clabe="123456789012345678"
            )
            cobro = apps.get_model("movimientos", "Cobro").objects.create(
                comercio_id=comercio.pk,
                canal="qr_venta",
                monto="10.00",
                concepto="Pan",
                pey_qr_id="qr-existente",
                qr_string="qr",
            )
            movimiento = apps.get_model("movimientos", "Movimiento").objects.create(
                comercio_id=comercio.pk,
                cobro_id=cobro.pk,
                canal="qr_venta",
                monto="10.00",
                concepto="Pan",
                origen="origen_desarrollo",
            )
            ejecutor = MigrationExecutor(connection)
            ejecutor.migrate(ejecutor.loader.graph.leaf_nodes())
            from ambito.models import Comercio
            from movimientos.models import Cobro, Movimiento

            actual = Comercio.objects.get(pk=comercio.pk)
            self.assertEqual(
                (actual.secuencia_evento, actual.clabe), (0, "123456789012345678")
            )
            cobro_actual = Cobro.objects.get(pk=cobro.pk)
            self.assertEqual(cobro_actual.concepto, "Pan")
            self.assertEqual(cobro_actual.pey_bank_account_id, "")
            self.assertEqual(
                Movimiento.objects.get(pk=movimiento.pk).cobro_id, cobro.pk
            )
        finally:
            ejecutor = MigrationExecutor(connection)
            ejecutor.migrate(ejecutor.loader.graph.leaf_nodes())
