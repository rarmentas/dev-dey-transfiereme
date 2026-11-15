"""Guardas del comando de designación demo."""

from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.test import TestCase, TransactionTestCase, override_settings

from ambito.admin import ComercioAdmin
from ambito.models import Comercio
from ambito.tests.soporte import crear_cuenta
from movimientos.models import Cobro

DESTINO = "01ARZ3NDEKTSV4RRFFQ69G5FAV"


@override_settings(DEMO_PEY_BANK_ACCOUNT_ID=DESTINO)
class DesignarDemoTests(TestCase):
    def setUp(self):
        self.a = Comercio.objects.create(nombre="Tienda reservada")
        self.b = Comercio.objects.create(nombre="B")

    def ejecutar(self, *args):
        salida = StringIO()
        call_command("designar_comercio_demo", *args, stdout=salida, stderr=salida)
        return salida.getvalue()

    def test_designar_estado_quitar_y_unicidad(self):
        self.ejecutar("--comercio", str(self.a.pk), "--si")
        self.a.refresh_from_db()
        self.assertTrue(self.a.es_demo)
        self.assertIn(DESTINO[-4:], self.ejecutar("--estado"))
        with self.assertRaises(CommandError):
            self.ejecutar("--comercio", str(self.b.pk), "--si")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Comercio.objects.filter(pk=self.b.pk).update(es_demo=True)
        self.ejecutar("--comercio", str(self.a.pk), "--quitar", "--si")
        self.a.refresh_from_db()
        self.assertFalse(self.a.es_demo)
        self.assertIn("es_demo", ComercioAdmin.readonly_fields)

    def test_log_estado_y_noop_no_filtran_datos(self):
        with self.assertLogs(
            "ambito.management.commands.designar_comercio_demo", level="WARNING"
        ) as logs:
            self.ejecutar("--comercio", str(self.a.pk), "--si")
        self.assertIn(f"comercio_id={self.a.pk} es_demo=True", logs.output[0])
        self.assertNotIn(self.a.nombre, logs.output[0])
        self.assertNotIn(DESTINO, logs.output[0])
        estado = self.ejecutar("--estado")
        self.assertIn(DESTINO[-4:], estado)
        self.assertNotIn(DESTINO, estado)
        self.assertIn(
            "Sin cambios", self.ejecutar("--comercio", str(self.a.pk), "--si")
        )
        self.ejecutar("--comercio", str(self.a.pk), "--quitar", "--si")
        self.assertIn(
            "Sin cambios",
            self.ejecutar("--comercio", str(self.a.pk), "--quitar", "--si"),
        )

    def test_id_invalido_o_inexistente_no_designan(self):
        for valor in ("letras", "99999999"):
            with self.subTest(valor=valor), self.assertRaises(CommandError):
                self.ejecutar("--comercio", valor, "--si")
        self.assertFalse(Comercio.objects.filter(es_demo=True).exists())

    def test_confirmacion(self):
        with (
            patch("sys.stdin.isatty", return_value=False),
            self.assertRaises(CommandError),
        ):
            self.ejecutar("--comercio", str(self.a.pk))
        with (
            patch("sys.stdin.isatty", return_value=True),
            patch("builtins.input", return_value="x"),
        ):
            with self.assertRaises(CommandError):
                self.ejecutar("--comercio", str(self.a.pk))
        self.a.refresh_from_db()
        self.assertFalse(self.a.es_demo)
        with (
            patch("sys.stdin.isatty", return_value=True),
            patch("builtins.input", return_value=str(self.a.pk)),
        ):
            self.ejecutar("--comercio", str(self.a.pk))
        self.a.refresh_from_db()
        self.assertTrue(self.a.es_demo)

    def test_rechaza_qr_colision_y_plaza(self):
        cuenta = crear_cuenta(self.b)
        cuenta.pey_bank_account_id = DESTINO
        cuenta.save(update_fields=["pey_bank_account_id"])
        with self.assertRaises(CommandError):
            self.ejecutar("--comercio", str(self.a.pk), "--si")
        cuenta.pey_bank_account_id = "01ARZ3NDEKTSV4RRFFQ69G5FAW"
        cuenta.save(update_fields=["pey_bank_account_id"])
        Cobro.objects.create(
            comercio=self.a,
            canal="qr_general",
            monto=0,
            concepto="",
            qr_string="qr",
            pey_qr_id="qr",
        )
        with self.assertRaises(CommandError):
            self.ejecutar("--comercio", str(self.a.pk), "--si")
        Cobro.objects.all().delete()
        with patch("pedidos.servicios.intentos.plaza_ocupada", return_value=True):
            with self.assertRaises(CommandError):
                self.ejecutar("--comercio", str(self.a.pk), "--si")
        self.a.refresh_from_db()
        self.assertFalse(self.a.es_demo)

    def test_quitar_rechaza_intento_vivo(self):
        from pedidos.models import IntentoCobro

        self.ejecutar("--comercio", str(self.a.pk), "--si")
        cuenta = crear_cuenta(self.a)
        IntentoCobro.objects.create(
            origen="legado",
            comercio=self.a,
            canal="qr_venta",
            estado="reservado",
            importe_efectivo_centavos=100,
            demo_mode=False,
            politica_cobro_version="normal-1",
            cuenta=cuenta,
            pey_bank_account_id=cuenta.pey_bank_account_id,
            concepto="venta",
            expiracion_s=600,
            clave_legado="ocupado",
        )
        with self.assertRaises(CommandError):
            self.ejecutar("--comercio", str(self.a.pk), "--quitar", "--si")
        self.a.refresh_from_db()
        self.assertTrue(self.a.es_demo)

    def test_venta_pendiente_bloquea_designar_y_quitar(self):
        from movimientos.models import Movimiento

        cobro = Cobro.objects.create(
            comercio=self.a,
            canal="qr_venta",
            monto="25.00",
            concepto="venta",
            qr_string="qr",
            pey_qr_id="venta-viva",
        )
        Movimiento.objects.create(
            comercio=self.a,
            cobro=cobro,
            canal="qr_venta",
            monto="25.00",
            concepto="venta",
            estado="pendiente",
            origen="origen_pey",
        )
        with self.assertRaises(CommandError):
            self.ejecutar("--comercio", str(self.a.pk), "--si")
        Comercio.objects.filter(pk=self.a.pk).update(es_demo=True)
        with self.assertRaises(CommandError):
            self.ejecutar("--comercio", str(self.a.pk), "--quitar", "--si")
        self.a.refresh_from_db()
        self.assertTrue(self.a.es_demo)

    @override_settings(DEMO_PEY_BANK_ACCOUNT_ID="")
    def test_sin_destino_advierte_y_lectura_fresca(self):
        from config.modo import modo_de_comercio

        self.assertIn(
            "no podrá cobrar", self.ejecutar("--comercio", str(self.a.pk), "--si")
        )
        self.assertFalse(self.a.es_demo)
        self.assertTrue(modo_de_comercio(self.a).demo)


class ConcurrenciaDemoTests(TransactionTestCase):
    def test_dos_designaciones_concurrentes_solo_una_prospera(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier

        from django.db import close_old_connections, connections

        comercios = [Comercio.objects.create(nombre=nombre) for nombre in ("A", "B")]
        barrera = Barrier(2)

        def designar(comercio):
            close_old_connections()
            try:
                barrera.wait()
                try:
                    call_command(
                        "designar_comercio_demo",
                        "--comercio",
                        str(comercio.pk),
                        "--si",
                        stdout=StringIO(),
                        stderr=StringIO(),
                    )
                    return "ok"
                except CommandError:
                    return "rechazado"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            resultados = list(pool.map(designar, comercios))
        self.assertCountEqual(resultados, ["ok", "rechazado"])
        self.assertEqual(Comercio.objects.filter(es_demo=True).count(), 1)
