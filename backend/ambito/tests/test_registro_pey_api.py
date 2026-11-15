"""Registro por cuenta y compatibilidad de la ruta anterior."""

import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from ambito.models import Comercio, Membresia
from ambito.tests.soporte import clabe_valida, crear_cuenta
from pey.cuentas import CuentaPey
from pey.tipos import ErrorPey

_ID = "01J9ZQ4C8X7Y6W5V4T3S2R1Q0P"


@override_settings(DEBUG=True, PEY_ADAPTADOR="produccion", PEY_API_KEY="prueba")
class RegistroPeyApiTests(TestCase):
    def setUp(self) -> None:
        self.comercio = Comercio.objects.create(nombre="Tienda")
        self.cuenta = crear_cuenta(
            self.comercio, estado="pending", predeterminada=False
        )
        self.cuenta.registro_estado = "sin_registro"
        self.cuenta.pey_bank_account_id = ""
        self.cuenta.save(update_fields=["registro_estado", "pey_bank_account_id"])
        self.usuario = User.objects.create_user(username="vend", password="pass")
        Membresia.objects.create(
            usuario=self.usuario, comercio=self.comercio, es_dueno=True
        )
        self.client = APIClient()
        self.client.force_login(self.usuario)
        self.ruta = f"/api/cuenta/cuentas/{self.cuenta.pk}/registro/"

    def _post(self, datos=None):
        cuerpo = {"nombre": "Ana", "entidad": "PERSON", "command_key": "clave",
                  "expected_version": 1}
        cuerpo.update(datos or {})
        return self.client.post(self.ruta, cuerpo, format="json")

    def test_registro_ok_guarda_ulid(self) -> None:
        with patch("ambito.operaciones_cuenta.registrar_cuenta",
                   return_value=CuentaPey(_ID, "PROCESSING")) as llamada:
            respuesta = self._post()
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(llamada.call_count, 1)
        self.cuenta.refresh_from_db()
        self.assertEqual(self.cuenta.pey_bank_account_id, _ID)
        self.assertNotIn(_ID, json.dumps(respuesta.json()))
        self.assertNotIn(self.cuenta.clabe, json.dumps(respuesta.json()))

    def test_sin_clabe_400(self) -> None:
        respuesta = self.client.post(
            "/api/cuenta/cuentas/", {"clabe": ""}, format="json"
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(respuesta.json()["codigo"], "CLABE_INVALIDA")

    def test_ya_registrada_409(self) -> None:
        self.cuenta.registro_estado = "registrado"
        self.cuenta.pey_bank_account_id = _ID
        self.cuenta.save(update_fields=["registro_estado", "pey_bank_account_id"])
        with patch("ambito.operaciones_cuenta.registrar_cuenta") as llamada:
            respuesta = self._post()
        self.assertEqual(respuesta.json()["codigo"], "CUENTA_YA_REGISTRADA")
        llamada.assert_not_called()

    def test_reemplazar_nuevo_id(self) -> None:
        respuesta = self.client.post("/api/cuenta/pey/registro/", {"reemplazar": True},
                                     format="json")
        self.assertEqual((respuesta.status_code, respuesta.json()["codigo"]),
                         (409, "USAR_CUENTAS"))
        self.cuenta.refresh_from_db()
        self.assertEqual(self.cuenta.pey_bank_account_id, "")

    def test_doble_registro_segundo_409(self) -> None:
        with patch("ambito.operaciones_cuenta.registrar_cuenta",
                   return_value=CuentaPey(_ID, "PENDING")) as llamada:
            uno = self._post()
            dos = self._post()
        self.assertEqual(uno.status_code, 200)
        self.assertEqual(dos.status_code, 200)
        self.assertTrue(dos.json()["replayed"])
        self.assertEqual(llamada.call_count, 1)

    def test_pey_incierto_503(self) -> None:
        with patch("ambito.operaciones_cuenta.registrar_cuenta", side_effect=ErrorPey(
            "NO_DISPONIBLE", "timeout", puede_haberse_creado=True
        )) as llamada:
            respuesta = self._post()
            otra = self._post()
        self.assertEqual(respuesta.json()["codigo"], "PEY_INCIERTO")
        self.assertEqual(respuesta.status_code, 503)
        self.assertEqual(otra.json()["codigo"], "REGISTRO_INCIERTO")
        self.assertEqual(llamada.call_count, 1)

    def test_pey_error_502(self) -> None:
        with patch("ambito.operaciones_cuenta.registrar_cuenta",
                   side_effect=ErrorPey("NOT_FOUND", "no")):
            respuesta = self._post()
        self.assertEqual((respuesta.status_code, respuesta.json()["codigo"]),
                         (502, "PEY_RECHAZO"))

    def test_comercio_en_cuerpo_400(self) -> None:
        self.assertEqual(self._post({"comercio_id": 99}).status_code, 400)

    def test_sin_sesion_403(self) -> None:
        self.client.logout()
        self.assertEqual(self._post().status_code, 403)

    @override_settings(DEBUG=True, PEY_ADAPTADOR="desarrollo", PEY_API_KEY="")
    def test_adaptador_desarrollo_503(self) -> None:
        respuesta = self._post()
        self.assertEqual((respuesta.status_code, respuesta.json()["codigo"]),
                         (503, "ADAPTADOR_NO_PRODUCCION"))

    def test_otro_comercio_no_afectado(self) -> None:
        comercio = Comercio.objects.create(nombre="B")
        cuenta = crear_cuenta(comercio, estado="pending", predeterminada=False)
        cuenta.clabe = clabe_valida(2)
        cuenta.save(update_fields=["clabe"])
        with patch("ambito.operaciones_cuenta.registrar_cuenta",
                   return_value=CuentaPey(_ID, "ACTIVE")):
            self.assertEqual(self._post().status_code, 200)
        cuenta.refresh_from_db()
        self.assertEqual(cuenta.codi_status, "pending")
