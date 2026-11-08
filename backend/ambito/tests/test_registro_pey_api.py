"""POST /api/cuenta/registro-pey/ — sin red; transporte parcheado."""

import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from ambito.models import Comercio, Membresia
from pey.tipos import ErrorPey
from sesion.middleware import _MENSAJE_SIN_SESION

_CLABE = "012180015826225713"
_ULID = "01J9ZQ4C8X7Y6W5V4T3S2R1Q0P"
_ULID_NUEVO = "01J9ZQ4C8X7Y6W5V4T3S2R1Q0M"
_RUTA = "/api/cuenta/pey/registro/"


class _Transporte:
    def __init__(self, status: int = 200, cuerpo: bytes = b"", side_effect=None) -> None:
        self.status = status
        self.cuerpo = cuerpo
        self.side_effect = side_effect
        self.llamadas: list = []

    def __call__(self, metodo, url, headers, cuerpo_bytes, timeout):
        self.llamadas.append((metodo, url, headers, cuerpo_bytes, timeout))
        if self.side_effect is not None:
            raise self.side_effect
        return self.status, self.cuerpo


@override_settings(
    DEBUG=True,
    PEY_ADAPTADOR="produccion",
    PEY_API_KEY="llave-falsa-test",
    PEY_BASE_URL="https://api.pey.mx",
)
class RegistroPeyApiTests(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.comercio = Comercio.objects.create(nombre="Tienda", clabe=_CLABE)
        self.usuario = User.objects.create_user(username="vend", password="pass")
        Membresia.objects.create(usuario=self.usuario, comercio=self.comercio)
        self.client.force_login(self.usuario)
        self.red = patch("urllib.request.urlopen", side_effect=AssertionError("red"))
        self.red.start()
        self.addCleanup(self.red.stop)

    def _post(self, cuerpo: dict):
        return self.client.post(_RUTA, cuerpo, format="json")

    def test_registro_ok_guarda_ulid(self) -> None:
        transporte = _Transporte(
            200,
            ('{"id": "' + _ULID_NUEVO + '", "codiStatus": "PROCESSING"}').encode(),
        )
        with patch("pey.cuentas.transporte_urllib", transporte):
            respuesta = self._post({"nombre": "Ana", "entidad": "PERSON"})
        self.assertEqual(respuesta.status_code, 200)
        cuerpo = respuesta.json()
        self.assertEqual(cuerpo["paso"], 3)
        self.assertTrue(cuerpo["tiene_cuenta_pey"])
        self.assertEqual(cuerpo["pey_bank_account_id_sufijo"], "1Q0M")
        self.assertEqual(len(transporte.llamadas), 1)
        self.comercio.refresh_from_db()
        self.assertEqual(self.comercio.pey_bank_account_id, _ULID_NUEVO)
        texto = json.dumps(cuerpo)
        self.assertNotIn(_CLABE, texto)
        self.assertNotIn(_ULID_NUEVO, texto)

    def test_sin_clabe_400(self) -> None:
        self.comercio.clabe = ""
        self.comercio.save()
        respuesta = self._post({"nombre": "Ana", "entidad": "PERSON"})
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(respuesta.json()["codigo"], "SIN_CLABE")

    def test_ya_registrada_409(self) -> None:
        """Caso borde 8."""
        self.comercio.pey_bank_account_id = _ULID
        self.comercio.save()
        transporte = _Transporte()
        with patch("pey.cuentas.transporte_urllib", transporte):
            respuesta = self._post({"nombre": "Ana", "entidad": "PERSON"})
        self.assertEqual(respuesta.status_code, 409)
        self.assertEqual(respuesta.json()["codigo"], "CUENTA_PEY_YA_REGISTRADA")
        self.assertEqual(transporte.llamadas, [])

    def test_reemplazar_nuevo_id(self) -> None:
        self.comercio.pey_bank_account_id = _ULID
        self.comercio.save()
        transporte = _Transporte(
            200,
            ('{"id": "' + _ULID_NUEVO + '", "codiStatus": "ACTIVE"}').encode(),
        )
        with patch("pey.cuentas.transporte_urllib", transporte):
            respuesta = self._post(
                {"nombre": "Ana", "entidad": "PERSON", "reemplazar": True},
            )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["fase"], "activa")

    def test_doble_registro_segundo_409(self) -> None:
        """Casos borde 3 y 4: doble clic / lock — un solo POST pey."""
        transporte = _Transporte(
            200,
            ('{"id": "' + _ULID_NUEVO + '", "codiStatus": "PENDING"}').encode(),
        )
        with patch("pey.cuentas.transporte_urllib", transporte):
            uno = self._post({"nombre": "Ana", "entidad": "PERSON"})
            dos = self._post({"nombre": "Ana", "entidad": "PERSON"})
        self.assertEqual(uno.status_code, 200)
        self.assertEqual(dos.status_code, 409)
        self.assertEqual(len(transporte.llamadas), 1)

    def test_pey_incierto_503(self) -> None:
        """Caso borde 7."""
        transporte = _Transporte(side_effect=TimeoutError("timeout"))
        with patch("pey.cuentas.transporte_urllib", transporte):
            respuesta = self._post({"nombre": "Ana", "entidad": "PERSON"})
        self.assertEqual(respuesta.status_code, 503)
        self.assertEqual(respuesta.json()["codigo"], "PEY_INCIERTO")

    def test_pey_error_502(self) -> None:
        transporte = _Transporte(
            404,
            b'{"error":{"message":"no","type":"NOT_FOUND","requestId":"req-x"}}',
        )
        with patch("pey.cuentas.transporte_urllib", transporte):
            respuesta = self._post({"nombre": "Ana", "entidad": "PERSON"})
        self.assertEqual(respuesta.status_code, 502)
        self.assertEqual(respuesta.json()["tipo"], "NOT_FOUND")

    def test_comercio_en_cuerpo_400(self) -> None:
        """Caso borde 14."""
        respuesta = self._post(
            {"nombre": "Ana", "entidad": "PERSON", "comercio_id": 99},
        )
        self.assertEqual(respuesta.status_code, 400)

    def test_sin_sesion_403(self) -> None:
        """Caso borde 13."""
        self.client.logout()
        respuesta = self._post({"nombre": "Ana", "entidad": "PERSON"})
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(respuesta.json()["detail"], _MENSAJE_SIN_SESION)

    @override_settings(DEBUG=True, PEY_ADAPTADOR="desarrollo", PEY_API_KEY="")
    def test_adaptador_desarrollo_503(self) -> None:
        respuesta = self._post({"nombre": "Ana", "entidad": "PERSON"})
        self.assertEqual(respuesta.status_code, 503)
        self.assertEqual(respuesta.json()["codigo"], "ADAPTADOR_NO_PRODUCCION")

    def test_otro_comercio_no_afectado(self) -> None:
        """Caso borde 9."""
        comercio_b = Comercio.objects.create(nombre="B", clabe=_CLABE)
        usuario_b = User.objects.create_user(username="b", password="pass")
        Membresia.objects.create(usuario=usuario_b, comercio=comercio_b)
        transporte = _Transporte(
            200,
            ('{"id": "' + _ULID_NUEVO + '", "codiStatus": "ACTIVE"}').encode(),
        )
        with patch("pey.cuentas.transporte_urllib", transporte):
            self._post({"nombre": "Ana", "entidad": "PERSON"})
        comercio_b.refresh_from_db()
        self.assertEqual(comercio_b.pey_bank_account_id, "")
