from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from ambito.models import Comercio, Membresia
from sesion.middleware import _MENSAJE_SIN_SESION

_RUTA = "/api/cuenta/comercio/"


class ComercioApiTests(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.comercio_a = Comercio.objects.create(nombre="Comercio A")
        self.comercio_b = Comercio.objects.create(nombre="Comercio B")
        self.usuario_a = User.objects.create_user(username="vendedor_a", password="pass-a")
        self.usuario_b = User.objects.create_user(username="vendedor_b", password="pass-b")
        Membresia.objects.create(usuario=self.usuario_a, comercio=self.comercio_a)
        Membresia.objects.create(usuario=self.usuario_b, comercio=self.comercio_b)

    def _entrar(self, usuario: User) -> None:
        self.client.force_login(usuario)

    def test_actualiza_nombre_del_comercio_de_la_sesion(self) -> None:
        self._entrar(self.usuario_a)
        respuesta = self.client.patch(
            _RUTA,
            {"nombre": "  Tortillería Norte  "},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["nombre"], "Tortillería Norte")
        self.assertEqual(respuesta.json()["id"], self.comercio_a.pk)
        self.comercio_a.refresh_from_db()
        self.comercio_b.refresh_from_db()
        self.assertEqual(self.comercio_a.nombre, "Tortillería Norte")
        self.assertEqual(self.comercio_b.nombre, "Comercio B")

    def test_rechaza_nombre_vacio(self) -> None:
        self._entrar(self.usuario_a)
        for cuerpo in ({"nombre": ""}, {"nombre": "   "}):
            with self.subTest(cuerpo=cuerpo):
                respuesta = self.client.patch(_RUTA, cuerpo, format="json")
                self.assertEqual(respuesta.status_code, 400)
        self.comercio_a.refresh_from_db()
        self.assertEqual(self.comercio_a.nombre, "Comercio A")

    def test_acepta_nombre_de_200_caracteres(self) -> None:
        self._entrar(self.usuario_a)
        nombre = "a" * 200
        respuesta = self.client.patch(_RUTA, {"nombre": nombre}, format="json")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["nombre"], nombre)
        self.comercio_a.refresh_from_db()
        self.assertEqual(self.comercio_a.nombre, nombre)

    def test_rechaza_nombre_largo(self) -> None:
        self._entrar(self.usuario_a)
        respuesta = self.client.patch(
            _RUTA,
            {"nombre": "x" * 201},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 400)
        self.comercio_a.refresh_from_db()
        self.assertEqual(self.comercio_a.nombre, "Comercio A")

    def test_rechaza_comercio_en_cuerpo(self) -> None:
        self._entrar(self.usuario_a)
        respuesta = self.client.patch(
            _RUTA,
            {"nombre": "Nuevo", "comercio_id": self.comercio_b.pk},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 400)

    def test_sin_sesion_403(self) -> None:
        respuesta = self.client.patch(_RUTA, {"nombre": "Nuevo"}, format="json")
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(respuesta.json()["detail"], _MENSAJE_SIN_SESION)
