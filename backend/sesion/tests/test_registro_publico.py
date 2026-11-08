import re
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from ambito.models import Comercio, Membresia
from sesion.models import CodigoCorreo

User = get_user_model()

_CODIGO_RE = re.compile(r"(?:código de confirmación es:|Su código es:)\s*(\d{6})")


def _codigo_desde_ultimo_correo() -> str:
    cuerpo = mail.outbox[-1].body
    coincidencia = _CODIGO_RE.search(cuerpo)
    assert coincidencia is not None, cuerpo
    return coincidencia.group(1)


class RegistroPublicoTests(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()

    def test_solicitar_y_confirmar_crea_cuenta_y_comercio(self) -> None:
        correo = "nuevo@ejemplo.mx"
        clave = "Clave-segura-9"

        solicitar = self.client.post(
            "/api/sesion/alta/solicitar/",
            {"correo": correo, "contraseña": clave},
            content_type="application/json",
        )
        self.assertEqual(solicitar.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)

        codigo = _codigo_desde_ultimo_correo()
        msg = mail.outbox[-1]
        self.assertEqual(len(msg.alternatives), 1)
        html, mime = msg.alternatives[0]
        self.assertEqual(mime, "text/html")
        self.assertIn(codigo, html)
        self.assertIn("Transfiéreme", html)
        self.assertIn("#1E4FA3", html)
        self.assertIn("#F4F6FA", html)
        self.assertIn("código de confirmación", html)
        confirmar = self.client.post(
            "/api/sesion/alta/confirmar/",
            {"correo": correo, "código": codigo},
            content_type="application/json",
        )
        self.assertEqual(confirmar.status_code, 200)

        usuario = User.objects.get(username=correo)
        membresia = Membresia.objects.get(usuario=usuario)
        comercio = membresia.comercio
        self.assertEqual(comercio.nombre, "Mi comercio")
        self.assertEqual(comercio.pey_codi_status, Comercio.PeyCodiStatus.PENDING)
        self.assertEqual(comercio.clabe, "")
        self.assertFalse(comercio.semilla_active_dev)

        entrar = self.client.post(
            "/api/sesion/entrar/",
            {"correo": correo, "contraseña": clave},
            content_type="application/json",
        )
        self.assertEqual(entrar.status_code, 200)

    def test_correo_ya_registrado(self) -> None:
        User.objects.create_user(
            username="existente@ejemplo.mx",
            email="existente@ejemplo.mx",
            password="clave-demo",
        )
        respuesta = self.client.post(
            "/api/sesion/alta/solicitar/",
            {"correo": "existente@ejemplo.mx", "contraseña": "Otra-clave-9"},
            content_type="application/json",
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("ya tiene cuenta", respuesta.json()["detail"])
        self.assertEqual(len(mail.outbox), 0)

    def test_confirmar_codigo_invalido(self) -> None:
        correo = "otro@ejemplo.mx"
        self.client.post(
            "/api/sesion/alta/solicitar/",
            {"correo": correo, "contraseña": "Otra-clave-9"},
            content_type="application/json",
        )
        confirmar = self.client.post(
            "/api/sesion/alta/confirmar/",
            {"correo": correo, "código": "000000"},
            content_type="application/json",
        )
        self.assertEqual(confirmar.status_code, 403)
        self.assertFalse(User.objects.filter(username=correo).exists())
        self.assertEqual(
            CodigoCorreo.objects.filter(correo=correo, usado_en__isnull=True).count(),
            1,
        )

    def test_confirmar_codigo_ya_usado(self) -> None:
        correo = "reuso@ejemplo.mx"
        clave = "Clave-segura-9"
        self.client.post(
            "/api/sesion/alta/solicitar/",
            {"correo": correo, "contraseña": clave},
            content_type="application/json",
        )
        codigo = _codigo_desde_ultimo_correo()
        primero = self.client.post(
            "/api/sesion/alta/confirmar/",
            {"correo": correo, "código": codigo},
            content_type="application/json",
        )
        self.assertEqual(primero.status_code, 200)
        segundo = self.client.post(
            "/api/sesion/alta/confirmar/",
            {"correo": correo, "código": codigo},
            content_type="application/json",
        )
        self.assertEqual(segundo.status_code, 403)

    def test_confirmar_codigo_vencido(self) -> None:
        correo = "vencido@ejemplo.mx"
        self.client.post(
            "/api/sesion/alta/solicitar/",
            {"correo": correo, "contraseña": "Clave-segura-9"},
            content_type="application/json",
        )
        codigo = _codigo_desde_ultimo_correo()
        solicitud = CodigoCorreo.objects.get(
            correo=correo,
            proposito=CodigoCorreo.Proposito.ALTA,
            usado_en__isnull=True,
        )
        solicitud.expira_en = timezone.now() - timedelta(minutes=1)
        solicitud.save(update_fields=["expira_en"])
        confirmar = self.client.post(
            "/api/sesion/alta/confirmar/",
            {"correo": correo, "código": codigo},
            content_type="application/json",
        )
        self.assertEqual(confirmar.status_code, 403)
        self.assertFalse(User.objects.filter(username=correo).exists())

    def test_dos_solicitudes_una_vigente(self) -> None:
        correo = "unico@ejemplo.mx"
        self.client.post(
            "/api/sesion/alta/solicitar/",
            {"correo": correo, "contraseña": "Clave-segura-9"},
            content_type="application/json",
        )
        codigo_antiguo = _codigo_desde_ultimo_correo()
        self.client.post(
            "/api/sesion/alta/solicitar/",
            {"correo": correo, "contraseña": "Clave-segura-9"},
            content_type="application/json",
        )
        self.assertEqual(
            CodigoCorreo.objects.filter(
                correo=correo,
                proposito=CodigoCorreo.Proposito.ALTA,
                usado_en__isnull=True,
            ).count(),
            1,
        )
        codigo_nuevo = _codigo_desde_ultimo_correo()
        self.assertNotEqual(codigo_antiguo, codigo_nuevo)
        mal = self.client.post(
            "/api/sesion/alta/confirmar/",
            {"correo": correo, "código": codigo_antiguo},
            content_type="application/json",
        )
        self.assertEqual(mal.status_code, 403)

    def test_contrasena_con_espacio_al_inicio_entra_igual(self) -> None:
        correo = "espacios@ejemplo.mx"
        clave = " Clave-segura-9"
        self.client.post(
            "/api/sesion/alta/solicitar/",
            {"correo": correo, "contraseña": clave},
            content_type="application/json",
        )
        codigo = _codigo_desde_ultimo_correo()
        self.client.post(
            "/api/sesion/alta/confirmar/",
            {"correo": correo, "código": codigo},
            content_type="application/json",
        )
        entrar = self.client.post(
            "/api/sesion/entrar/",
            {"correo": correo, "contraseña": clave},
            content_type="application/json",
        )
        self.assertEqual(entrar.status_code, 200)

    @patch("sesion.codigos.enviar_codigo_correo", side_effect=OSError("smtp caído"))
    def test_solicitar_falla_envio_devuelve_error(self, _mock) -> None:
        respuesta = self.client.post(
            "/api/sesion/alta/solicitar/",
            {"correo": "falla@ejemplo.mx", "contraseña": "Clave-segura-9"},
            content_type="application/json",
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("correo", respuesta.json()["detail"].lower())
        self.assertFalse(
            CodigoCorreo.objects.filter(
                correo="falla@ejemplo.mx",
                usado_en__isnull=True,
            ).exists(),
        )
