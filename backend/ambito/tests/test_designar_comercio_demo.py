"""Guardas del comando de designación demo."""

from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.test import TestCase, TransactionTestCase, override_settings

from ambito.admin import ComercioAdmin
from ambito.models import Comercio, Membresia
from ambito.tests.soporte import crear_cuenta
from movimientos.alta_qr_general import alta_qr_general
from movimientos.exceptions import DemoBloqueado
from movimientos.models import Cobro, Movimiento

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

    def test_rechaza_colision_con_cuenta_propia_o_ajena(self):
        for comercio in (self.a, self.b):
            with self.subTest(comercio=comercio.pk):
                cuenta = crear_cuenta(comercio)
                original = cuenta.pey_bank_account_id
                cuenta.pey_bank_account_id = DESTINO
                cuenta.save(update_fields=["pey_bank_account_id"])
                with self.assertRaisesMessage(
                    CommandError,
                    "El destino demo coincide con una cuenta registrada.",
                ):
                    self.ejecutar("--comercio", str(self.a.pk), "--si")
                self.a.refresh_from_db()
                self.assertFalse(self.a.es_demo)
                cuenta.pey_bank_account_id = original
                cuenta.save(update_fields=["pey_bank_account_id"])

    def test_historial_qr_general_se_conserva_al_designar_y_quitar(self):
        cuenta = crear_cuenta(self.a)
        cobro = Cobro.objects.create(
            comercio=self.a,
            cuenta=cuenta,
            canal="qr_general",
            monto=0,
            concepto="Transferencia",
            qr_string="qr",
            pey_qr_id="qr-historial",
            pey_bank_account_id=cuenta.pey_bank_account_id,
        )
        movimiento = Movimiento.objects.create(
            comercio=self.a,
            cobro=cobro,
            canal="qr_general",
            monto="25.00",
            concepto="Transferencia",
            estado="pagado",
            origen="origen_pey",
        )
        campos_cobro = Cobro.objects.filter(pk=cobro.pk).values().get()
        campos_movimiento = Movimiento.objects.filter(pk=movimiento.pk).values().get()
        for quitar in (False, True):
            args = ["--comercio", str(self.a.pk), "--si"]
            if quitar:
                args.append("--quitar")
            self.ejecutar(*args)
            self.a.refresh_from_db()
            self.assertEqual(self.a.es_demo, not quitar)
            self.assertEqual(
                Cobro.objects.filter(pk=cobro.pk).values().get(), campos_cobro
            )
            self.assertEqual(
                Movimiento.objects.filter(pk=movimiento.pk).values().get(),
                campos_movimiento,
            )

    def test_qr_general_existente_no_se_puede_solicitar_en_demo(self):
        Cobro.objects.create(
            comercio=self.a,
            canal="qr_general",
            monto=0,
            concepto="Transferencia",
            qr_string="qr",
            pey_qr_id="qr-existente",
        )
        self.ejecutar("--comercio", str(self.a.pk), "--si")
        self.a.refresh_from_db()
        usuario = get_user_model().objects.create_user(username="demo-qr")
        Membresia.objects.create(usuario=usuario, comercio=self.a)
        self.client.force_login(usuario)
        with patch("movimientos.alta_qr_general.obtener_puerto") as obtener:
            with self.assertRaises(DemoBloqueado):
                alta_qr_general(self.a)
            respuesta = self.client.post(
                "/api/cobro/qr-general/", {}, content_type="application/json"
            )
            obtener.assert_not_called()
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(respuesta.json()["codigo"], "RUTA_BLOQUEADA_EN_DEMO")
        self.assertEqual(Cobro.objects.filter(comercio=self.a).count(), 1)

    def test_quitar_no_revisa_colision_del_destino(self):
        self.ejecutar("--comercio", str(self.a.pk), "--si")
        cuenta = crear_cuenta(self.b)
        cuenta.pey_bank_account_id = DESTINO
        cuenta.save(update_fields=["pey_bank_account_id"])
        self.ejecutar("--comercio", str(self.a.pk), "--quitar", "--si")
        self.a.refresh_from_db()
        self.assertFalse(self.a.es_demo)

    def test_qr_general_con_intento_vivo_bloquea_designar_y_quitar(self):
        from pedidos.models import IntentoCobro

        cuenta = crear_cuenta(self.a)
        Cobro.objects.create(
            comercio=self.a,
            cuenta=cuenta,
            canal="qr_general",
            monto=0,
            concepto="Transferencia",
            qr_string="qr",
            pey_qr_id="qr-general-intento",
            pey_bank_account_id=cuenta.pey_bank_account_id,
        )
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
        with self.assertRaisesMessage(CommandError, "plaza ocupada"):
            self.ejecutar("--comercio", str(self.a.pk), "--si")
        self.a.refresh_from_db()
        self.assertFalse(self.a.es_demo)
        Comercio.objects.filter(pk=self.a.pk).update(es_demo=True)
        with self.assertRaisesMessage(CommandError, "plaza ocupada"):
            self.ejecutar("--comercio", str(self.a.pk), "--quitar", "--si")
        self.a.refresh_from_db()
        self.assertTrue(self.a.es_demo)

    def test_venta_pendiente_bloquea_designar_y_quitar(self):
        Cobro.objects.create(
            comercio=self.a,
            canal="qr_general",
            monto=0,
            concepto="Transferencia",
            qr_string="qr",
            pey_qr_id="qr-general-plaza",
        )
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
        with self.assertRaisesMessage(CommandError, "plaza ocupada"):
            self.ejecutar("--comercio", str(self.a.pk), "--si")
        self.a.refresh_from_db()
        self.assertFalse(self.a.es_demo)
        Comercio.objects.filter(pk=self.a.pk).update(es_demo=True)
        with self.assertRaisesMessage(CommandError, "plaza ocupada"):
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
