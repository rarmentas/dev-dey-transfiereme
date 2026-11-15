from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings

from ambito.models import Comercio, Membresia


class TokenAsistenteVivoTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user("tendero", password="secreto")
        comercio = Comercio.objects.create(nombre="Abarrotes")
        Membresia.objects.create(usuario=self.user, comercio=comercio)
        self.client.force_login(self.user)

    def test_sin_clave_devuelve_503(self):
        with override_settings(GEMINI_API_KEY=""):
            response = self.client.post("/api/asistente-vivo/token/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["codigo"], "ASISTENTE_NO_CONFIGURADO")

    def test_sin_sesion_es_rechazado(self):
        self.client.logout()
        response = self.client.post("/api/asistente-vivo/token/")
        self.assertIn(response.status_code, (401, 403))

    @override_settings(GEMINI_API_KEY="clave-de-prueba")
    @patch("asistente_vivo.views.crear_cliente")
    def test_emite_token_acotado(self, crear_cliente):
        crear_cliente.return_value.auth_tokens.create.return_value = SimpleNamespace(name="ephemeral-token")
        response = self.client.post("/api/asistente-vivo/token/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["token"], "ephemeral-token")
        config = crear_cliente.return_value.auth_tokens.create.call_args.kwargs["config"]
        self.assertEqual(config["uses"], 1)
        self.assertIn("live_connect_constraints", config)
        self.assertIn("tools", config["live_connect_constraints"]["config"])

    @override_settings(GEMINI_API_KEY="clave-de-prueba", GEMINI_LIVE_MAX_SESIONES_HORA=1)
    @patch("asistente_vivo.views.crear_cliente")
    def test_limita_sesiones(self, crear_cliente):
        crear_cliente.return_value.auth_tokens.create.return_value = SimpleNamespace(name="uno")
        self.assertEqual(self.client.post("/api/asistente-vivo/token/").status_code, 200)
        cache.delete(f"asistente-vivo:activo:{self.user.pk}")
        response = self.client.post("/api/asistente-vivo/token/")
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["codigo"], "LIMITE_SESIONES")
