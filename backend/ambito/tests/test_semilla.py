import inspect

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from ambito.cuenta import cuenta_esta_active
from ambito.models import Comercio, Membresia
from movimientos.models import Movimiento


@override_settings(DEBUG=True)
class SemillaVendedorTests(TestCase):
    def test_comando_deja_sesion_en_su_comercio_sin_movimientos(self) -> None:
        call_command(
            "sembrar_vendedor",
            correo="vendedor@demo.mx",
            contraseña="clave-demo",
        )

        usuario = User.objects.get(username="vendedor@demo.mx")
        comercio = usuario.membresia.comercio
        self.assertEqual(comercio.nombre, "Comercio demo")
        self.assertTrue(comercio.semilla_active_dev)
        self.assertFalse(cuenta_esta_active(comercio))
        self.assertEqual(Movimiento.objects.count(), 0)

        cliente = APIClient()
        entrar = cliente.post(
            "/api/sesion/entrar/",
            {"correo": "vendedor@demo.mx", "contraseña": "clave-demo"},
            format="json",
        )
        self.assertEqual(entrar.status_code, 200)
        estado = cliente.get("/api/sesion/estado/")
        self.assertEqual(estado.status_code, 200)
        self.assertEqual(estado.json()["comercio"]["id"], comercio.pk)
        listado = cliente.get("/api/movimientos/")
        self.assertEqual(listado.status_code, 200)
        self.assertEqual(listado.json(), [])

    def test_repetir_el_comando_no_duplica_ni_crea_movimientos(self) -> None:
        call_command("sembrar_vendedor", contraseña="clave-demo")
        call_command("sembrar_vendedor", contraseña="otra-clave")

        self.assertEqual(User.objects.filter(username="vendedor@demo.mx").count(), 1)
        self.assertEqual(Comercio.objects.filter(semilla_active_dev=True).count(), 1)
        self.assertEqual(Membresia.objects.count(), 1)
        self.assertEqual(Movimiento.objects.count(), 0)
        self.assertTrue(User.objects.get(username="vendedor@demo.mx").check_password("otra-clave"))

    def test_la_semilla_no_satisface_el_gate_active(self) -> None:
        fuente = inspect.getsource(cuenta_esta_active)
        self.assertNotIn("semilla_active_dev", fuente)
        comercio = Comercio.objects.create(nombre="Solo semilla", semilla_active_dev=True)
        self.assertFalse(cuenta_esta_active(comercio))

    @override_settings(DEBUG=False)
    def test_no_corre_fuera_de_desarrollo(self) -> None:
        with self.assertRaises(CommandError):
            call_command("sembrar_vendedor", contraseña="clave-demo")
