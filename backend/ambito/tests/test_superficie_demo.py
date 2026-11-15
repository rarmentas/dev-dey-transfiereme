"""El indicador demo no es editable ni visible en las superficies públicas."""

import ast
import json
import os
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from django.urls import path
from rest_framework.test import APIClient

from ambito.admin import ComercioAdmin
from ambito.models import Comercio, Membresia
from ambito.tests.soporte import clabe_valida, crear_cuenta
from config import modo

urlpatterns = [path("admin/", admin.site.urls)]


class SuperficieDemoTests(TestCase):
    def setUp(self):
        self.comercio = Comercio.objects.create(nombre="Tienda")
        self.cuenta = crear_cuenta(self.comercio)
        self.usuario = get_user_model().objects.create_superuser(
            username="dueno", password="clave", email="dueno@example.test"
        )
        Membresia.objects.create(
            usuario=self.usuario, comercio=self.comercio, es_dueno=True
        )
        self.cliente = APIClient()
        self.cliente.force_login(self.usuario)

    def test_apis_no_exponen_ni_cambian_demo(self):
        rutas = (
            ("/api/cuenta/comercio/", {"nombre": "Nuevo", "es_demo": True}),
            ("/api/cuenta/clabe/", {"clabe": clabe_valida(3), "es_demo": True}),
            ("/api/cuenta/cuentas/", {"clabe": clabe_valida(4), "es_demo": True}),
            (
                f"/api/cuenta/cuentas/{self.cuenta.pk}/predeterminada/",
                {"es_demo": True},
            ),
            (f"/api/cuenta/cuentas/{self.cuenta.pk}/registro/", {"es_demo": True}),
            (f"/api/cuenta/cuentas/{self.cuenta.pk}/sincronizar/", {"es_demo": True}),
            ("/api/cuenta/pey/registro/", {"es_demo": True}),
            ("/api/cuenta/pey/sincronizar/", {"es_demo": True}),
            ("/api/pedidos/", {"es_demo": True}),
        )
        with (
            patch("django.core.management.call_command") as comando,
            patch("ambito.views_cuentas.registrar", return_value=(self.cuenta, False)),
            patch("ambito.views_cuentas.sincronizar", return_value=self.cuenta),
        ):
            for ruta, datos in rutas:
                for metodo in ("post", "patch"):
                    with self.subTest(ruta=ruta, metodo=metodo):
                        respuesta = getattr(self.cliente, metodo)(
                            ruta, datos, format="json"
                        )
                        self.assertNotIn("es_demo", respuesta.content.decode())
                        self.comercio.refresh_from_db()
                        self.assertFalse(self.comercio.es_demo)
            for ruta in (
                "/api/sesion/estado/",
                "/api/cuenta/cuentas/",
                "/api/cuenta/clabe/",
                "/api/cuenta/pey/estado/",
            ):
                respuesta = self.cliente.get(ruta)
                self.assertEqual(respuesta.status_code, 200)
                self.assertNotIn("es_demo", json.dumps(respuesta.json()))
            Comercio.objects.filter(pk=self.comercio.pk).update(es_demo=True)
            for ruta, datos in (
                ("/api/cuenta/comercio/", {"nombre": "Otro", "es_demo": False}),
                ("/api/cuenta/clabe/", {"es_demo": False}),
                ("/api/cuenta/cuentas/", {"clabe": clabe_valida(5), "es_demo": False}),
            ):
                for metodo in ("post", "patch"):
                    respuesta = getattr(self.cliente, metodo)(
                        ruta, datos, format="json"
                    )
                    self.assertNotIn("es_demo", respuesta.content.decode())
                    self.comercio.refresh_from_db()
                    self.assertTrue(self.comercio.es_demo)
            comando.assert_not_called()

    def test_tendero_no_expone_ni_modifica_indicador(self):
        from uuid import uuid4
        from pedidos.models import Pedido

        pedido = Pedido.objects.create(
            comercio=self.comercio,
            numero=1,
            instancia_id="instancia",
            sesion_id="sesion",
            conversacion_id="conversacion",
            cliente_externo_id="c",
            mensaje_origen_id=uuid4(),
            message_key_origen="mensaje",
            secuencia_conversacion_aplicada=1,
        )
        base = f"/api/pedidos/{pedido.pk}/"
        for sufijo in ("cotizaciones/", "cobro/", "listo/", "entregado/", "renglones/"):
            for metodo in ("post", "patch", "put"):
                datos = {
                    "command_key": "clave",
                    "expected_version": 1,
                    "renglones": [],
                    "es_demo": True,
                }
                respuesta = getattr(self.cliente, metodo)(
                    base + sufijo, datos, format="json"
                )
                self.assertNotIn("es_demo", respuesta.content.decode())
                self.comercio.refresh_from_db()
                self.assertFalse(self.comercio.es_demo)
        for ruta in ("/api/pedidos/", base):
            respuesta = self.cliente.get(ruta)
            self.assertEqual(respuesta.status_code, 200)
            self.assertNotIn("es_demo", respuesta.content.decode())

    def test_admin_muestra_campo_solo_lectura_y_formulario_no_lo_altera(self):
        modelo_admin = ComercioAdmin(Comercio, admin.site)
        request = RequestFactory().post("/")
        request.user = self.usuario
        self.assertIn("es_demo", modelo_admin.list_display)
        self.assertIn(
            "es_demo", modelo_admin.get_readonly_fields(request, self.comercio)
        )
        formulario = modelo_admin.get_form(request, self.comercio)(
            {"nombre": "Editado", "es_demo": "on", "secuencia_evento": "0"},
            instance=self.comercio,
        )
        self.assertNotIn("es_demo", formulario.fields)
        self.assertTrue(formulario.is_valid(), formulario.errors)
        formulario.save()
        self.comercio.refresh_from_db()
        self.assertFalse(self.comercio.es_demo)

    @override_settings(ROOT_URLCONF=__name__)
    def test_post_admin_ignora_es_demo(self):
        respuesta = self.cliente.post(
            f"/admin/ambito/comercio/{self.comercio.pk}/change/",
            {
                "nombre": "Editado",
                "secuencia_evento": "0",
                "es_demo": "on",
                "_save": "Guardar",
            },
        )
        self.assertEqual(respuesta.status_code, 302, respuesta.content)
        self.comercio.refresh_from_db()
        self.assertEqual(self.comercio.nombre, "Editado")
        self.assertFalse(self.comercio.es_demo)

    @override_settings(
        DEBUG=False, NUCLEO_ADAPTADOR="real", PEDIDOS_COBRO_HABILITADO=False
    )
    def test_entorno_antiguo_advierte_y_no_designacion(self):
        with patch.dict(
            os.environ, {"DEMO_MODE": "true", "POLITICA_COBRO_VERSION": "demo-1"}
        ):
            with self.assertLogs("config.modo", level="WARNING") as logs:
                modo.validar_configuracion()
        self.assertEqual(len(logs.records), 2)
        self.assertFalse(hasattr(settings, "DEMO_MODE"))
        self.assertFalse(hasattr(settings, "POLITICA_COBRO_VERSION"))
        self.assertFalse(Comercio.objects.filter(es_demo=True).exists())
        self.assertFalse(modo.modo_de_comercio(self.comercio).demo)

    def test_arranque_real_ignora_variables_globales(self):
        import subprocess
        import sys

        entorno = os.environ.copy()
        entorno.update(DEMO_MODE="true", POLITICA_COBRO_VERSION="demo-1")
        backend = Path(__file__).resolve().parents[2]
        resultado = subprocess.run(
            [sys.executable, "manage.py", "check"],
            cwd=backend,
            env=entorno,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertIn("DEMO_MODE ignorada", resultado.stderr)
        self.assertIn("POLITICA_COBRO_VERSION ignorada", resultado.stderr)
        self.assertFalse(Comercio.objects.filter(es_demo=True).exists())

    def test_vistas_no_invocan_comando_operador(self):
        raiz = Path(__file__).resolve().parents[2]
        vistas = list(raiz.glob("*/views*.py"))
        self.assertTrue(vistas)
        for archivo in vistas:
            arbol = ast.parse(archivo.read_text())
            textos = [
                n.value
                for n in ast.walk(arbol)
                if isinstance(n, ast.Constant) and isinstance(n.value, str)
            ]
            nombres = [n.name for n in ast.walk(arbol) if isinstance(n, ast.alias)]
            self.assertFalse(
                any("designar_comercio_demo" in s for s in textos + nombres), archivo
            )
