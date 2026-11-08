from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from ambito.models import Comercio, Membresia
from movimientos.models import Movimiento


def _vendedor(correo: str = "vendedor@demo.mx"):
    comercio = Comercio.objects.create(nombre="Comercio demo", semilla_active_dev=True)
    usuario = User.objects.create_user(username=correo, email=correo, password="clave")
    Membresia.objects.create(usuario=usuario, comercio=comercio)
    return usuario, comercio


class SembrarMovimientosDemoTests(TestCase):
    @override_settings(DEBUG=False)
    def test_sin_debug_rechaza(self) -> None:
        with self.assertRaises(CommandError):
            call_command("sembrar_movimientos_demo")

    @override_settings(DEBUG=True)
    def test_crea_y_la_segunda_vez_no_duplica(self) -> None:
        _vendedor()
        call_command("sembrar_movimientos_demo")
        primero = set(Movimiento.objects.values_list("pk", flat=True))
        self.assertEqual(len(primero), 12)

        call_command("sembrar_movimientos_demo")
        self.assertEqual(
            set(Movimiento.objects.values_list("pk", flat=True)),
            primero,
        )

    @override_settings(DEBUG=True)
    def test_reset_recrea_solo_los_demo(self) -> None:
        _, comercio = _vendedor()
        call_command("sembrar_movimientos_demo")
        ajeno = Movimiento.objects.create(
            comercio=comercio,
            monto=Decimal("9.00"),
            concepto="Cobro real",
            canal=Movimiento.Canal.QR_VENTA,
            origen=Movimiento.Origen.ORIGEN_PEY,
            estado=Movimiento.Estado.PAGADO,
            pagado_en=Movimiento.objects.get(
                pey_transaction_id="demo-pago-01"
            ).pagado_en,
        )
        anteriores = set(
            Movimiento.objects.exclude(pk=ajeno.pk).values_list("pk", flat=True)
        )

        call_command("sembrar_movimientos_demo", reset=True)

        self.assertTrue(Movimiento.objects.filter(pk=ajeno.pk).exists())
        nuevos = set(
            Movimiento.objects.exclude(pk=ajeno.pk).values_list("pk", flat=True)
        )
        self.assertEqual(len(nuevos), 12)
        self.assertTrue(anteriores.isdisjoint(nuevos))

    @override_settings(DEBUG=True)
    def test_tablero_del_vendedor_solo_trae_desarrollo(self) -> None:
        usuario, comercio = _vendedor()
        call_command("sembrar_movimientos_demo")
        cliente = APIClient()
        cliente.force_login(usuario)

        respuesta = cliente.get("/api/movimientos/tablero/")
        self.assertEqual(respuesta.status_code, 200)
        cuerpo = respuesta.json()
        self.assertEqual(cuerpo["confirmado"]["filas"], [])
        self.assertEqual(cuerpo["confirmado"]["total"], "0.00")
        self.assertGreater(len(cuerpo["desarrollo"]["filas"]), 0)

        pagados = Movimiento.objects.filter(
            comercio=comercio,
            estado=Movimiento.Estado.PAGADO,
            origen=Movimiento.Origen.ORIGEN_DESARROLLO,
        )
        esperado = sum((movimiento.monto for movimiento in pagados), Decimal("0"))
        self.assertEqual(
            cuerpo["desarrollo"]["total"],
            format(esperado.quantize(Decimal("0.01")), "f"),
        )
        canales = {fila["canal"] for fila in cuerpo["desarrollo"]["filas"]}
        self.assertTrue(
            canales
            <= {
                Movimiento.Canal.QR_GENERAL,
                Movimiento.Canal.QR_VENTA,
                Movimiento.Canal.NOTIFICACION,
            }
        )
        self.assertEqual(Movimiento.objects.filter(estado=Movimiento.Estado.PENDIENTE).count(), 1)
        self.assertEqual(Movimiento.objects.filter(estado=Movimiento.Estado.VENCIDO).count(), 1)
