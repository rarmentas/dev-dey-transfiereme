from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.contrib.auth.models import User
from django.db import close_old_connections, connections
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient

from ambito.cuentas_servicio import alta
from ambito.models import Comercio, Membresia
from ambito.operaciones_cuenta import ErrorOperacion
from ambito.tests.soporte import clabe_valida


class CuentasApiAcTests(TestCase):
    def setUp(self):
        self.comercio = Comercio.objects.create(nombre="A")
        usuario = User.objects.create_user(username="a")
        Membresia.objects.create(comercio=self.comercio, usuario=usuario, es_dueno=True)
        self.client = APIClient()
        self.client.force_login(usuario)
        self.ruta = "/api/cuenta/cuentas/"

    def test_ac1_11_dueno_guarda_y_lista_dos_clabe_sin_sobrescribir(self):
        self.assertEqual(self.client.get(self.ruta).json()["cuentas"], [])
        for n in (1, 2):
            self.assertEqual(
                self.client.post(
                    self.ruta, {"clabe": clabe_valida(n)}, format="json"
                ).status_code,
                201,
            )
        cuentas = self.client.get(self.ruta).json()["cuentas"]
        self.assertEqual(len(cuentas), 2)
        self.assertEqual(
            set(self.comercio.cuentas.values_list("clabe", flat=True)),
            {clabe_valida(1), clabe_valida(2)},
        )
        self.assertNotEqual(cuentas[0]["id"], cuentas[1]["id"])

    def test_ac1_12_clabe_invalida_duplicada_y_ceros_iniciales(self):
        for n in (1, 2):
            self.assertEqual(
                self.client.post(
                    self.ruta, {"clabe": clabe_valida(n)}, format="json"
                ).status_code,
                201,
            )
        tercera = clabe_valida(3)
        con_verificador_malo = tercera[:-1] + str((int(tercera[-1]) + 1) % 10)
        for invalida, codigo in (
            ("", 400),
            ("²" * 18, 400),
            (con_verificador_malo, 400),
            (clabe_valida(3)[:-1] + "X", 400),
            (clabe_valida(1), 409),
        ):
            respuesta = self.client.post(self.ruta, {"clabe": invalida}, format="json")
            self.assertEqual(respuesta.status_code, codigo)
        self.assertEqual(
            set(self.comercio.cuentas.values_list("clabe", flat=True)),
            {clabe_valida(1), clabe_valida(2)},
        )
        self.assertTrue(
            all(c.startswith("0") for c in (clabe_valida(1), clabe_valida(2)))
        )

    def test_otro_comercio_no_ve_ni_modifica(self):
        respuesta = self.client.post(
            self.ruta, {"clabe": clabe_valida(1)}, format="json"
        )
        cuenta_id = respuesta.json()["cuenta"]["id"]
        otro = Comercio.objects.create(nombre="B")
        usuario = User.objects.create_user(username="b")
        Membresia.objects.create(comercio=otro, usuario=usuario, es_dueno=True)
        self.client.force_login(usuario)
        self.assertEqual(self.client.get(self.ruta).json()["cuentas"], [])
        for accion in ("registro", "sincronizar", "predeterminada"):
            respuesta = self.client.post(
                f"{self.ruta}{cuenta_id}/{accion}/", {}, format="json"
            )
            self.assertEqual(respuesta.status_code, 404)
        self.assertEqual(self.comercio.cuentas.count(), 1)
        self.assertFalse(otro.cuentas.exists())


class CuentasApiConcurrenciaTests(TransactionTestCase):
    def test_alta_duplicada_concurrente_crea_una(self):
        comercio = Comercio.objects.create(nombre="Concurrente")
        barrera = Barrier(2)

        def crear():
            close_old_connections()
            try:
                barrera.wait()
                try:
                    alta(Comercio.objects.get(pk=comercio.pk), clabe_valida(1))
                    return "creada"
                except ErrorOperacion as exc:
                    return exc.codigo
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            resultados = list(executor.map(lambda _: crear(), range(2)))
        self.assertCountEqual(resultados, ["creada", "CLABE_DUPLICADA"])
        self.assertEqual(comercio.cuentas.count(), 1)
