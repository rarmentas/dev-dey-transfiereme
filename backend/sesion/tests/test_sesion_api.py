import json

from django.contrib.auth.models import User
from django.test import Client, TestCase
from rest_framework.test import APIClient

from ambito.models import Comercio, Membresia


class SesionApiTests(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.comercio = Comercio.objects.create(nombre="Comercio demo")
        self.usuario = User.objects.create_user(
            username="vendedor@demo.mx",
            email="vendedor@demo.mx",
            password="clave-demo",
        )
        Membresia.objects.create(usuario=self.usuario, comercio=self.comercio)

    def test_entrar_ok_deja_sesion(self) -> None:
        respuesta = self.client.post(
            "/api/sesion/entrar/",
            {"correo": "vendedor@demo.mx", "contraseña": "clave-demo"},
            content_type="application/json",
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["usuario"], "vendedor@demo.mx")

        estado = self.client.get("/api/sesion/estado/")
        self.assertEqual(estado.status_code, 200)
        cuerpo = estado.json()
        self.assertEqual(cuerpo["usuario"], "vendedor@demo.mx")
        self.assertEqual(cuerpo["correo"], "vendedor@demo.mx")
        self.assertEqual(cuerpo["comercio"]["id"], self.comercio.pk)
        self.assertEqual(cuerpo["comercio"]["nombre"], "Comercio demo")

    def test_entrar_credenciales_malas(self) -> None:
        respuesta = self.client.post(
            "/api/sesion/entrar/",
            {"correo": "vendedor@demo.mx", "contraseña": "incorrecta"},
            content_type="application/json",
        )
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(respuesta.json()["detail"], "Revise el correo y la contraseña.")

    def test_estado_sin_sesion(self) -> None:
        respuesta = self.client.get("/api/sesion/estado/")
        self.assertEqual(respuesta.status_code, 403)

    def test_salir_cierra_sesion(self) -> None:
        self.client.post(
            "/api/sesion/entrar/",
            {"correo": "vendedor@demo.mx", "contraseña": "clave-demo"},
            content_type="application/json",
        )
        salir = self.client.post("/api/sesion/salir/")
        self.assertEqual(salir.status_code, 200)
        estado = self.client.get("/api/sesion/estado/")
        self.assertEqual(estado.status_code, 403)

    def test_salir_sin_csrf_solo_cookie_de_sesion(self) -> None:
        cliente = Client(enforce_csrf_checks=True)
        credenciales = json.dumps(
            {"correo": "vendedor@demo.mx", "contraseña": "clave-demo"},
        )
        entrar = cliente.post(
            "/api/sesion/entrar/",
            credenciales,
            content_type="application/json",
        )
        self.assertEqual(entrar.status_code, 200)

        antes = cliente.get("/api/sesion/estado/")
        self.assertEqual(antes.status_code, 200)

        salir = cliente.post("/api/sesion/salir/")
        self.assertEqual(salir.status_code, 200)

        despues = cliente.get("/api/sesion/estado/")
        self.assertEqual(despues.status_code, 403)

    def test_entrar_por_email_distinto_de_username(self) -> None:
        User.objects.create_user(
            username="login_por_correo",
            email="unico@demo.mx",
            password="clave-unica",
        )
        usuario = User.objects.get(username="login_por_correo")
        Membresia.objects.create(usuario=usuario, comercio=self.comercio)

        respuesta = self.client.post(
            "/api/sesion/entrar/",
            {"correo": "unico@demo.mx", "contraseña": "clave-unica"},
            content_type="application/json",
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["usuario"], "login_por_correo")
