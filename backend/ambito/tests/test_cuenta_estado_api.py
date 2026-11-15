"""GET /api/cuenta/ — estado sin exponer CLABE ni ULID completo."""

import json

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from ambito.models import Comercio, Membresia
from ambito.tests.soporte import crear_cuenta
from sesion.middleware import _MENSAJE_SIN_SESION

_CLABE = "012180015826225713"
_ULID = "01J9ZQ4C8X7Y6W5V4T3S2R1Q0P"
_RUTA = "/api/cuenta/pey/estado/"


def _sin_secretos(cuerpo: object, clabe: str, ulid: str) -> None:
    texto = json.dumps(cuerpo, ensure_ascii=False)
    assert clabe not in texto
    assert ulid not in texto


class CuentaEstadoApiTests(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.comercio_a = Comercio.objects.create(nombre="Comercio A")
        self.cuenta = crear_cuenta(
            self.comercio_a, estado="pending", predeterminada=False
        )
        self.cuenta.clabe = _CLABE
        self.cuenta.pey_bank_account_id = ""
        self.cuenta.registro_estado = "sin_registro"
        self.cuenta.save()
        self.comercio_b = Comercio.objects.create(nombre="Comercio B")
        self.usuario_a = User.objects.create_user(
            username="vendedor_a", password="pass-a"
        )
        self.usuario_b = User.objects.create_user(
            username="vendedor_b", password="pass-b"
        )
        Membresia.objects.create(usuario=self.usuario_a, comercio=self.comercio_a)
        Membresia.objects.create(usuario=self.usuario_b, comercio=self.comercio_b)

    def _entrar(self, usuario: User) -> None:
        self.client.force_login(usuario)

    def test_sin_clabe_paso_1(self) -> None:
        self._entrar(self.usuario_b)
        respuesta = self.client.get(_RUTA)
        self.assertEqual(respuesta.status_code, 200)
        cuerpo = respuesta.json()
        self.assertEqual(cuerpo["fase"], "sin_clabe")
        self.assertEqual(cuerpo["paso"], 1)
        self.assertFalse(cuerpo["puede_cobrar"])
        _sin_secretos(cuerpo, _CLABE, _ULID)

    def test_pendiente_registro_paso_2(self) -> None:
        self._entrar(self.usuario_a)
        respuesta = self.client.get(_RUTA)
        cuerpo = respuesta.json()
        self.assertEqual(cuerpo["fase"], "pendiente_registro")
        self.assertEqual(cuerpo["paso"], 2)
        self.assertTrue(cuerpo["clabe_enmascarada"].endswith("5713"))

    def test_pendiente_activacion_paso_3(self) -> None:
        self.cuenta.pey_bank_account_id = _ULID
        self.cuenta.registro_estado = "registrado"
        self.cuenta.save()
        self._entrar(self.usuario_a)
        cuerpo = self.client.get(_RUTA).json()
        self.assertEqual(cuerpo["fase"], "pendiente_activacion")
        self.assertEqual(cuerpo["paso"], 3)
        self.assertEqual(cuerpo["pey_bank_account_id_sufijo"], "1Q0P")

    @override_settings(DEBUG=True, PEY_ADAPTADOR="desarrollo", PEY_API_KEY="")
    def test_activa_con_semilla_dev(self) -> None:
        self._activar()
        self._entrar(self.usuario_a)
        cuerpo = self.client.get(_RUTA).json()
        self.assertEqual(cuerpo["fase"], "activa")
        self.assertIsNone(cuerpo["paso"])
        self.assertTrue(cuerpo["puede_cobrar"])

    def test_otro_comercio_solo_ve_el_suyo(self) -> None:
        self._activar()
        self._entrar(self.usuario_b)
        cuerpo = self.client.get(_RUTA).json()
        self.assertEqual(cuerpo["fase"], "sin_clabe")
        self._entrar(self.usuario_a)
        cuerpo_a = self.client.get(_RUTA).json()
        self.assertEqual(cuerpo_a["fase"], "activa")

    def test_sin_sesion_403(self) -> None:
        respuesta = self.client.get(_RUTA)
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(respuesta.json()["detail"], _MENSAJE_SIN_SESION)

    def test_tras_cambio_clabe_vuelve_paso_2(self) -> None:
        """La ruta anterior no altera el estado activo."""
        self._activar()
        self._entrar(self.usuario_a)
        respuesta = self.client.post(
            "/api/cuenta/clabe/", {"clabe": "032180000118359719"}, format="json"
        )
        self.assertEqual(respuesta.status_code, 409)
        cuerpo = self.client.get(_RUTA).json()
        self.assertEqual(cuerpo["fase"], "activa")
        self.assertTrue(cuerpo["tiene_cuenta_pey"])

    def _activar(self) -> None:
        self.cuenta.registro_estado = "registrado"
        self.cuenta.pey_bank_account_id = _ULID
        self.cuenta.codi_status = "active"
        self.cuenta.save()
        self.comercio_a.cuenta_por_defecto = self.cuenta
        self.comercio_a.save(update_fields=["cuenta_por_defecto"])
