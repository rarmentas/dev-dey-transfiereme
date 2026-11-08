import json
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from ambito.cuenta_sync import sincronizar_codi_status
from ambito.models import Comercio, Membresia
from movimientos.models import Cobro, Movimiento
from sesion.middleware import _MENSAJE_SIN_SESION

_RUTA = "/api/cobro/qr-general/"
_CLABE_VALIDA = "012180015826225713"
_CLAVES_PROHIBIDAS = ("PEY_API_KEY", "PEY_WEBHOOK_SECRET", "api.pey.mx")


def _revienta(*args, **kwargs):
    raise AssertionError("no debe haber red")


def _cuerpo_sin_secretos(cuerpo: object) -> None:
    texto = json.dumps(cuerpo, ensure_ascii=False)
    for clave in _CLAVES_PROHIBIDAS:
        assert clave not in texto, f"Apareció «{clave}» en la respuesta"


@override_settings(DEBUG=True, PEY_API_KEY="", PEY_ADAPTADOR="desarrollo")
class AltaQrGeneralApiTests(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.comercio_activo = Comercio.objects.create(
            nombre="Comercio activo",
            clabe=_CLABE_VALIDA,
            semilla_active_dev=True,
        )
        self.comercio_pendiente = Comercio.objects.create(
            nombre="Comercio pendiente",
            clabe=_CLABE_VALIDA,
            semilla_active_dev=False,
        )
        sincronizar_codi_status(self.comercio_activo)
        sincronizar_codi_status(self.comercio_pendiente)
        self.usuario_activo = User.objects.create_user(
            username="vendedor_activo",
            password="pass-activo",
        )
        self.usuario_pendiente = User.objects.create_user(
            username="vendedor_pendiente",
            password="pass-pendiente",
        )
        Membresia.objects.create(
            usuario=self.usuario_activo,
            comercio=self.comercio_activo,
        )
        Membresia.objects.create(
            usuario=self.usuario_pendiente,
            comercio=self.comercio_pendiente,
        )

    def _entrar(self, usuario: User) -> None:
        self.client.force_login(usuario)

    @patch("urllib.request.urlopen", _revienta)
    @patch("socket.socket.connect", _revienta)
    def test_active_simulado_persiste_qr_string_sin_movimiento_pagado(self) -> None:
        self._entrar(self.usuario_activo)
        respuesta = self.client.post(_RUTA, {}, format="json")
        self.assertEqual(respuesta.status_code, 201)
        cuerpo = respuesta.json()
        _cuerpo_sin_secretos(cuerpo)
        self.assertTrue(cuerpo["qr_string"].startswith("cody-dev://qr/"))
        self.assertTrue(cuerpo["pey_qr_id"].startswith("dev-qr-"))

        cobro = Cobro.objects.get(comercio=self.comercio_activo)
        self.assertEqual(cobro.qr_string, cuerpo["qr_string"])
        self.assertEqual(cobro.pey_qr_id, cuerpo["pey_qr_id"])
        self.assertEqual(cobro.canal, Movimiento.Canal.QR_GENERAL)
        self.assertEqual(cobro.monto, Decimal("0"))
        self.assertEqual(cobro.concepto, "Transferencia")
        self.assertEqual(
            Movimiento.objects.filter(estado=Movimiento.Estado.PAGADO).count(),
            0,
        )

    def test_cuenta_pendiente_error_sin_cobro_ni_pagado(self) -> None:
        self._entrar(self.usuario_pendiente)
        respuesta = self.client.post(_RUTA, {}, format="json")
        self.assertEqual(respuesta.status_code, 400)
        cuerpo = respuesta.json()
        self.assertEqual(cuerpo["tipo"], "INVALID_STATE")
        self.assertEqual(Cobro.objects.count(), 0)
        self.assertEqual(
            Movimiento.objects.filter(estado=Movimiento.Estado.PAGADO).count(),
            0,
        )

    @patch("urllib.request.urlopen", _revienta)
    @patch("socket.socket.connect", _revienta)
    def test_segundo_post_devuelve_mismo_qr_sin_segundo_crear(self) -> None:
        self._entrar(self.usuario_activo)
        primera = self.client.post(_RUTA, {}, format="json")
        self.assertEqual(primera.status_code, 201)
        with patch(
            "pey.desarrollo.AdaptadorDesarrollo.crear_qr",
            side_effect=AssertionError("no debe invocarse de nuevo"),
        ):
            segunda = self.client.post(_RUTA, {}, format="json")
        self.assertEqual(segunda.status_code, 200)
        self.assertEqual(segunda.json()["qr_string"], primera.json()["qr_string"])
        self.assertEqual(Cobro.objects.filter(comercio=self.comercio_activo).count(), 1)

    def test_rechaza_comercio_en_cuerpo(self) -> None:
        self._entrar(self.usuario_activo)
        respuesta = self.client.post(
            _RUTA,
            {"comercio": self.comercio_pendiente.pk},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(Cobro.objects.count(), 0)

    def test_sin_sesion_403(self) -> None:
        respuesta = self.client.post(_RUTA, {}, format="json")
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(respuesta.json()["detail"], _MENSAJE_SIN_SESION)

    @patch("urllib.request.urlopen", _revienta)
    @patch("socket.socket.connect", _revienta)
    def test_cada_comercio_obtiene_su_propio_qr(self) -> None:
        comercio_b = Comercio.objects.create(
            nombre="Comercio B",
            clabe=_CLABE_VALIDA,
            semilla_active_dev=True,
        )
        sincronizar_codi_status(comercio_b)
        usuario_b = User.objects.create_user(username="vendedor_b", password="pass-b")
        Membresia.objects.create(usuario=usuario_b, comercio=comercio_b)

        self._entrar(self.usuario_activo)
        respuesta_a = self.client.post(_RUTA, {}, format="json")
        self.assertEqual(respuesta_a.status_code, 201)

        self.client.logout()
        self._entrar(usuario_b)
        respuesta_b = self.client.post(_RUTA, {}, format="json")
        self.assertEqual(respuesta_b.status_code, 201)
        self.assertNotEqual(
            respuesta_a.json()["pey_qr_id"],
            respuesta_b.json()["pey_qr_id"],
        )
        self.assertEqual(Cobro.objects.count(), 2)
