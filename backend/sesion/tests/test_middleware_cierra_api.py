from django.contrib.auth.models import AnonymousUser, User
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from rest_framework.test import APIClient

from ambito.models import Comercio, Membresia

from sesion.middleware import CierraApiSinSesionMiddleware, _MENSAJE_SIN_SESION


def _ejecutar_middleware(request: object) -> HttpResponse:
    def vista_dummy(req: object) -> HttpResponse:
        return HttpResponse("ok", status=200)

    return CierraApiSinSesionMiddleware(vista_dummy)(request)


class CierraApiSinSesionMiddlewareTests(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.factory = RequestFactory()
        self.comercio = Comercio.objects.create(nombre="Comercio demo")
        self.usuario = User.objects.create_user(
            username="vendedor@demo.mx",
            email="vendedor@demo.mx",
            password="clave-demo",
        )
        Membresia.objects.create(usuario=self.usuario, comercio=self.comercio)

    def test_post_cobro_sin_cookie_devuelve_403(self) -> None:
        respuesta = self.client.post(
            "/api/cobro/",
            {},
            content_type="application/json",
        )
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(respuesta.json()["detail"], _MENSAJE_SIN_SESION)

    def test_salir_get_sin_cookie_bloqueado_en_middleware(self) -> None:
        respuesta = self.client.get("/api/sesion/salir/")
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(respuesta.json()["detail"], _MENSAJE_SIN_SESION)

    def test_entrar_credenciales_validas_sin_regression(self) -> None:
        respuesta = self.client.post(
            "/api/sesion/entrar/",
            {"correo": "vendedor@demo.mx", "contraseña": "clave-demo"},
            content_type="application/json",
        )
        self.assertEqual(respuesta.status_code, 200)

    def test_estado_sin_sesion_pasa_middleware_y_drf_responde_403(self) -> None:
        respuesta = self.client.get("/api/sesion/estado/")
        self.assertEqual(respuesta.status_code, 403)
        self.assertNotEqual(respuesta.json().get("detail"), _MENSAJE_SIN_SESION)

    def test_webhook_pey_sin_sesion_no_recibe_403_del_middleware(self) -> None:
        respuesta = self.client.post(
            "/api/webhooks/pey/",
            {},
            content_type="application/json",
        )
        self.assertNotEqual(respuesta.status_code, 403)

    def test_salud_get_sin_cookie(self) -> None:
        respuesta = self.client.get("/api/salud/")
        self.assertEqual(respuesta.status_code, 200)

    def test_unit_post_cobro_request_factory(self) -> None:
        request = self.factory.post("/api/cobro/", data="{}", content_type="application/json")
        request.user = AnonymousUser()
        respuesta = _ejecutar_middleware(request)
        self.assertEqual(respuesta.status_code, 403)
        self.assertIn(_MENSAJE_SIN_SESION, respuesta.content.decode())

    def test_unit_webhook_passthrough_request_factory(self) -> None:
        request = self.factory.post(
            "/api/webhooks/pey/",
            data="{}",
            content_type="application/json",
        )
        request.user = AnonymousUser()
        respuesta = _ejecutar_middleware(request)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.content.decode(), "ok")
