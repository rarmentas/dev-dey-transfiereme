"""Compatibilidad de CLABE y alta en la API de cuentas."""

import json

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from ambito.models import Comercio, Membresia
from ambito.tests.soporte import clabe_valida, crear_cuenta


class ClabeApiTests(TestCase):
    def setUp(self) -> None:
        self.comercio_a = Comercio.objects.create(nombre="A")
        self.comercio_b = Comercio.objects.create(nombre="B")
        self.usuario_a = User.objects.create_user(username="a", password="pass")
        self.usuario_b = User.objects.create_user(username="b", password="pass")
        Membresia.objects.create(
            usuario=self.usuario_a, comercio=self.comercio_a, es_dueno=True
        )
        Membresia.objects.create(
            usuario=self.usuario_b, comercio=self.comercio_b, es_dueno=True
        )
        self.client = APIClient()

    def _entrar(self, usuario):
        self.client.force_login(usuario)

    def test_get_clabe_vacia_sin_guardar(self) -> None:
        self._entrar(self.usuario_a)
        self.assertEqual(self.client.get("/api/cuenta/clabe/").json(), {"clabe": ""})

    def test_get_clabe_del_comercio_de_la_sesion(self) -> None:
        cuenta = crear_cuenta(self.comercio_a)
        self._entrar(self.usuario_a)
        self.assertEqual(self.client.get("/api/cuenta/clabe/").json()["clabe"],
                         "*" * 14 + cuenta.clabe[-4:])
        self._entrar(self.usuario_b)
        self.assertEqual(self.client.get("/api/cuenta/clabe/").json()["clabe"], "")

    def test_get_no_cambia_pey_ni_clabe_persistida(self) -> None:
        cuenta = crear_cuenta(self.comercio_a)
        self._entrar(self.usuario_a)
        self.client.get("/api/cuenta/clabe/")
        cuenta.refresh_from_db()
        self.assertEqual(cuenta.clabe, clabe_valida(1))
        self.assertEqual(cuenta.codi_status, "active")
        self.assertTrue(cuenta.pey_bank_account_id)

    def test_get_clabe_sin_sesion_403(self) -> None:
        self.assertEqual(self.client.get("/api/cuenta/clabe/").status_code, 403)

    def test_persiste_clabe_en_cuenta_del_comercio(self) -> None:
        self._entrar(self.usuario_a)
        respuesta = self.client.post("/api/cuenta/cuentas/", {"clabe": clabe_valida(1)},
                                     format="json")
        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(self.comercio_a.cuentas.get().clabe, clabe_valida(1))
        self.assertFalse(self.comercio_b.cuentas.exists())

    def test_rechaza_comercio_en_cuerpo(self) -> None:
        self._entrar(self.usuario_a)
        for clave in ("comercio", "comercio_id"):
            respuesta = self.client.post(
                "/api/cuenta/cuentas/",
                {"clabe": clabe_valida(1), clave: self.comercio_b.pk},
                format="json",
            )
            self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(self.comercio_a.cuentas.exists())

    def test_clabe_invalida_no_persiste(self) -> None:
        self._entrar(self.usuario_a)
        respuesta = self.client.post(
            "/api/cuenta/cuentas/", {"clabe": "123"}, format="json"
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(respuesta.json()["codigo"], "CLABE_INVALIDA")
        self.assertFalse(self.comercio_a.cuentas.exists())

    def test_sin_sesion_403(self) -> None:
        self.assertEqual(
            self.client.post("/api/cuenta/cuentas/", {}, format="json").status_code, 403
        )

    def test_respuestas_no_exponen_secretos_plataforma(self) -> None:
        cuenta = crear_cuenta(self.comercio_a)
        self._entrar(self.usuario_a)
        cuerpo = json.dumps(self.client.get("/api/cuenta/cuentas/").json())
        self.assertNotIn(cuenta.clabe, cuerpo)
        self.assertNotIn(cuenta.pey_bank_account_id, cuerpo)
        self.assertNotIn("PEY_API_KEY", cuerpo)
        self.assertNotIn("PEY_WEBHOOK_SECRET", cuerpo)
