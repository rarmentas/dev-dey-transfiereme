import re
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from ambito.models import Comercio, Membresia
from sesion.models import CodigoCorreo

_CODIGO_RE = re.compile(r"Su código es:\s*(\d{6})")


def _codigo_desde_ultimo_correo() -> str:
    cuerpo = mail.outbox[-1].body
    coincidencia = _CODIGO_RE.search(cuerpo)
    assert coincidencia is not None, cuerpo
    return coincidencia.group(1)


class OlvidoContrasenaTests(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.comercio = Comercio.objects.create(nombre="Comercio demo")
        self.usuario = User.objects.create_user(
            username="vendedor@demo.mx",
            email="vendedor@demo.mx",
            password="clave-vieja",
        )
        Membresia.objects.create(usuario=self.usuario, comercio=self.comercio)

    def test_solicitar_misma_respuesta_sin_usuario(self) -> None:
        con = self.client.post(
            "/api/sesion/olvido/solicitar/",
            {"correo": "vendedor@demo.mx"},
            content_type="application/json",
        )
        sin = self.client.post(
            "/api/sesion/olvido/solicitar/",
            {"correo": "nadie@ejemplo.mx"},
            content_type="application/json",
        )
        self.assertEqual(con.status_code, 200)
        self.assertEqual(sin.status_code, 200)
        self.assertEqual(con.json()["detail"], sin.json()["detail"])
        self.assertEqual(len(mail.outbox), 1)

    def test_restablecer_y_entrar(self) -> None:
        self.client.post(
            "/api/sesion/olvido/solicitar/",
            {"correo": "vendedor@demo.mx"},
            content_type="application/json",
        )
        codigo = _codigo_desde_ultimo_correo()
        nueva = "Nueva-clave-9"
        restablecer = self.client.post(
            "/api/sesion/olvido/restablecer/",
            {
                "correo": "vendedor@demo.mx",
                "código": codigo,
                "contraseña": nueva,
            },
            content_type="application/json",
        )
        self.assertEqual(restablecer.status_code, 200)

        mal = self.client.post(
            "/api/sesion/entrar/",
            {"correo": "vendedor@demo.mx", "contraseña": "clave-vieja"},
            content_type="application/json",
        )
        self.assertEqual(mal.status_code, 403)

        bien = self.client.post(
            "/api/sesion/entrar/",
            {"correo": "vendedor@demo.mx", "contraseña": nueva},
            content_type="application/json",
        )
        self.assertEqual(bien.status_code, 200)

    @patch("sesion.codigos.enviar_codigo_correo", side_effect=OSError("smtp caído"))
    def test_solicitar_smtp_falla_misma_respuesta(self, _mock) -> None:
        detalle_ok = "Si existe una cuenta con ese correo, recibirá un código en breve."
        respuesta = self.client.post(
            "/api/sesion/olvido/solicitar/",
            {"correo": "vendedor@demo.mx"},
            content_type="application/json",
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["detail"], detalle_ok)

    def test_restablecer_codigo_ya_usado(self) -> None:
        self.client.post(
            "/api/sesion/olvido/solicitar/",
            {"correo": "vendedor@demo.mx"},
            content_type="application/json",
        )
        codigo = _codigo_desde_ultimo_correo()
        primera = "Nueva-clave-9"
        ok = self.client.post(
            "/api/sesion/olvido/restablecer/",
            {
                "correo": "vendedor@demo.mx",
                "código": codigo,
                "contraseña": primera,
            },
            content_type="application/json",
        )
        self.assertEqual(ok.status_code, 200)
        segunda = self.client.post(
            "/api/sesion/olvido/restablecer/",
            {
                "correo": "vendedor@demo.mx",
                "código": codigo,
                "contraseña": "Otra-clave-9",
            },
            content_type="application/json",
        )
        self.assertEqual(segunda.status_code, 403)

    def test_restablecer_codigo_vencido(self) -> None:
        self.client.post(
            "/api/sesion/olvido/solicitar/",
            {"correo": "vendedor@demo.mx"},
            content_type="application/json",
        )
        codigo = _codigo_desde_ultimo_correo()
        solicitud = CodigoCorreo.objects.get(
            correo="vendedor@demo.mx",
            proposito=CodigoCorreo.Proposito.OLVIDO,
            usado_en__isnull=True,
        )
        solicitud.expira_en = timezone.now() - timedelta(minutes=1)
        solicitud.save(update_fields=["expira_en"])
        respuesta = self.client.post(
            "/api/sesion/olvido/restablecer/",
            {
                "correo": "vendedor@demo.mx",
                "código": codigo,
                "contraseña": "Nueva-clave-9",
            },
            content_type="application/json",
        )
        self.assertEqual(respuesta.status_code, 403)
