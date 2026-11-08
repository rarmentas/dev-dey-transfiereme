import json
import os
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from ambito.models import Comercio, Membresia
from sesion.middleware import _MENSAJE_SIN_SESION

CLABE_OFICIAL = "012180015826225713"
_FALSO_SECRETO = "secreto-falso-para-test"
_CLAVES_PROHIBIDAS = ("PEY_API_KEY", "PEY_WEBHOOK_SECRET", _FALSO_SECRETO)
_RUTA_CLABE = "/api/cuenta/clabe/"


def _cuerpo_sin_secretos(cuerpo: object) -> None:
    texto = json.dumps(cuerpo, ensure_ascii=False)
    for clave in _CLAVES_PROHIBIDAS:
        assert clave not in texto, f"Apareció «{clave}» en la respuesta"


class ClabeApiTests(TestCase):
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

    def test_persiste_clabe_en_comercio_de_la_sesion(self) -> None:
        self._entrar(self.usuario_a)
        respuesta = self.client.post(
            _RUTA_CLABE,
            {"clabe": CLABE_OFICIAL},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["clabe"], CLABE_OFICIAL)
        self.comercio_a.refresh_from_db()
        self.comercio_b.refresh_from_db()
        self.assertEqual(self.comercio_a.clabe, CLABE_OFICIAL)
        self.assertEqual(self.comercio_b.clabe, "")

    def test_rechaza_comercio_en_cuerpo(self) -> None:
        self._entrar(self.usuario_a)
        for cuerpo in (
            {"clabe": CLABE_OFICIAL, "comercio": self.comercio_b.pk},
            {"clabe": CLABE_OFICIAL, "comercio_id": self.comercio_b.pk},
        ):
            with self.subTest(cuerpo=cuerpo):
                respuesta = self.client.post(_RUTA_CLABE, cuerpo, format="json")
                self.assertEqual(respuesta.status_code, 400)
                self.assertIn("comercio", respuesta.json()["detail"].lower())

    def test_clabe_invalida_no_persiste(self) -> None:
        self._entrar(self.usuario_a)
        clabe_mala = CLABE_OFICIAL[:-1] + ("0" if CLABE_OFICIAL[-1] != "0" else "1")
        respuesta = self.client.post(_RUTA_CLABE, {"clabe": clabe_mala}, format="json")
        self.assertEqual(respuesta.status_code, 400)
        self.comercio_a.refresh_from_db()
        self.assertEqual(self.comercio_a.clabe, "")

    def test_sin_sesion_403(self) -> None:
        respuesta = self.client.post(
            _RUTA_CLABE,
            {"clabe": CLABE_OFICIAL},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(respuesta.json()["detail"], _MENSAJE_SIN_SESION)

    @mock.patch.dict(os.environ, {"PEY_API_KEY": _FALSO_SECRETO}, clear=False)
    def test_respuestas_no_exponen_secretos_plataforma(self) -> None:
        self._entrar(self.usuario_a)
        guardar = self.client.post(
            _RUTA_CLABE,
            {"clabe": CLABE_OFICIAL},
            format="json",
        )
        self.assertEqual(guardar.status_code, 200)
        _cuerpo_sin_secretos(guardar.json())

        estado = self.client.get("/api/sesion/estado/")
        self.assertEqual(estado.status_code, 200)
        _cuerpo_sin_secretos(estado.json())
