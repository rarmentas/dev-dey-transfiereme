from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class MigracionesTests(TransactionTestCase):
    def test_secuencia_conserva_comercio_existente(self) -> None:
        ejecutor = MigrationExecutor(connection)
        anterior = [("ambito", "0004_comercio_pey_codi_status")]
        # La migración inicial de pedidos depende de la nueva columna.
        ejecutor.migrate([("pedidos", None), *anterior])
        estado = ejecutor.loader.project_state(anterior)
        comercio = estado.apps.get_model("ambito", "Comercio")
        pk = comercio.objects.create(nombre="Existente").pk
        ejecutor = MigrationExecutor(connection)
        ejecutor.migrate(ejecutor.loader.graph.leaf_nodes())
        from ambito.models import Comercio

        self.assertEqual(Comercio.objects.get(pk=pk).secuencia_evento, 0)
