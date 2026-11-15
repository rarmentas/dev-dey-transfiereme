from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import close_old_connections, connections
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient

from ambito.cuenta import cuenta_esta_active
from ambito.cuentas_servicio import alta, elegir_default
from ambito.models import Comercio, Membresia
from ambito.operaciones_cuenta import (
    ErrorOperacion,
    sincronizar,
)
from ambito.tests.soporte import clabe_valida, crear_cuenta
from pey.tipos import ErrorPey


class CuentasApiTests(TestCase):
    def setUp(self):
        self.comercio = Comercio.objects.create(nombre="A")
        self.usuario = User.objects.create_user(username="dueño")
        self.membresia = Membresia.objects.create(
            usuario=self.usuario, comercio=self.comercio, es_dueno=True
        )
        self.client = APIClient()
        self.client.force_login(self.usuario)

    def test_dos_clabes_con_ceros_y_duplicado(self):
        for n in (1, 2):
            respuesta = self.client.post(
                "/api/cuenta/cuentas/", {"clabe": clabe_valida(n)}, format="json"
            )
            self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(
            list(
                self.comercio.cuentas.order_by("clabe").values_list("clabe", flat=True)
            ),
            [clabe_valida(1), clabe_valida(2)],
        )
        respuesta = self.client.post(
            "/api/cuenta/cuentas/", {"clabe": clabe_valida(1)}, format="json"
        )
        self.assertEqual(
            (respuesta.status_code, respuesta.json()["codigo"]),
            (409, "CLABE_DUPLICADA"),
        )

    def test_permisos_y_ambito(self):
        ajena = crear_cuenta(Comercio.objects.create(nombre="B"))
        url = f"/api/cuenta/cuentas/{ajena.pk}/predeterminada/"
        self.assertEqual(
            self.client.post(url, {"expected_version": 1}).status_code, 404
        )
        self.membresia.es_dueno = False
        self.membresia.save(update_fields=["es_dueno"])
        self.assertEqual(self.client.get("/api/cuenta/cuentas/").status_code, 403)
        self.assertEqual(
            self.client.get("/api/cuenta/cuentas/?comercio=1").status_code, 400
        )
        self.client.logout()
        self.assertEqual(self.client.get("/api/cuenta/cuentas/").status_code, 403)

    def test_default_apta_y_endpoints_viejos(self):
        cuenta = crear_cuenta(self.comercio, predeterminada=False)
        url = f"/api/cuenta/cuentas/{cuenta.pk}/predeterminada/"
        respuesta = self.client.post(
            url, {"expected_version": cuenta.version}, format="json"
        )
        self.assertEqual(respuesta.status_code, 200)
        self.comercio.refresh_from_db()
        self.assertTrue(cuenta_esta_active(self.comercio))
        self.assertEqual(
            self.client.get("/api/cuenta/clabe/").json()["clabe"],
            "*" * 14 + cuenta.clabe[-4:],
        )
        for ruta in ("clabe/", "pey/registro/", "pey/sincronizar/"):
            respuesta = self.client.post("/api/cuenta/" + ruta, {}, format="json")
            self.assertEqual(
                (respuesta.status_code, respuesta.json()["codigo"]),
                (409, "USAR_CUENTAS"),
            )
        cuenta.codi_status = "pending"
        cuenta.save(update_fields=["codi_status"])
        self.assertFalse(cuenta_esta_active(self.comercio))
        self.comercio.refresh_from_db()
        self.assertEqual(self.comercio.cuenta_por_defecto_id, cuenta.pk)

    def test_default_rechaza_pendiente_y_version_obsoleta(self):
        anterior = crear_cuenta(self.comercio)
        pendiente = crear_cuenta(self.comercio, estado="pending", predeterminada=False)
        url = f"/api/cuenta/cuentas/{pendiente.pk}/predeterminada/"
        respuesta = self.client.post(url, {"expected_version": 1}, format="json")
        self.assertEqual(respuesta.json()["codigo"], "CUENTA_NO_ELEGIBLE")
        respuesta = self.client.post(url, {"expected_version": 99}, format="json")
        self.assertEqual(respuesta.json()["codigo"], "VERSION_OBSOLETA")
        self.comercio.refresh_from_db()
        self.assertEqual(self.comercio.cuenta_por_defecto_id, anterior.pk)

    def test_sync_404_conserva_id_y_bloquea_cobro(self):
        cuenta = crear_cuenta(self.comercio)
        ident = cuenta.pey_bank_account_id
        with patch(
            "ambito.operaciones_cuenta.consultar_cuenta",
            side_effect=ErrorPey("BANK_ACCOUNT_NOT_FOUND", ""),
        ):
            sincronizar(cuenta)
        cuenta.refresh_from_db()
        self.assertEqual(cuenta.pey_bank_account_id, ident)
        self.assertEqual(cuenta.codi_status, "pending")
        self.assertFalse(cuenta_esta_active(self.comercio))


class ConcurrenciaCuentasTests(TransactionTestCase):
    def test_alta_duplicada_y_defaults_concurrentes(self):
        comercio = Comercio.objects.create(nombre="A")
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
        comercio.cuentas.all().delete()
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
