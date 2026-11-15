"""Validación de la configuración de cobro por comercio."""

import os
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings

from config.modo import politica_de, validar_configuracion


class ConfiguracionTests(SimpleTestCase):
    @override_settings(
        DEBUG=False, NUCLEO_ADAPTADOR="real", PEDIDOS_COBRO_HABILITADO=False
    )
    def test_produccion_sin_modo_global(self):
        with patch.dict(os.environ, {}, clear=True):
            validar_configuracion()
        self.assertEqual(politica_de(False), "normal-1")
        self.assertEqual(politica_de(True), "demo-1")

    @override_settings(PEDIDOS_COBRO_HABILITADO=False)
    def test_variables_obsoletas_se_ignoran(self):
        for valor in ("true", "otro"):
            with (
                self.subTest(valor=valor),
                patch.dict(os.environ, {"DEMO_MODE": valor}),
            ):
                with self.assertLogs("config.modo", level="WARNING"):
                    validar_configuracion()

    @override_settings(
        DEMO_PEY_BANK_ACCOUNT_ID="invalido", PEDIDOS_COBRO_HABILITADO=False
    )
    def test_destino_invalido_no_impide_arranque(self):
        with (
            patch.dict(os.environ, {"DEMO_PEY_BANK_ACCOUNT_ID": "invalido"}),
            self.assertLogs("config.modo", level="WARNING") as logs,
        ):
            validar_configuracion()
        self.assertIn("DEMO_PEY_BANK_ACCOUNT_ID ignorada", logs.output[0])

    @override_settings(DEBUG=True, PEDIDOS_COBRO_HABILITADO=True)
    def test_cobro_no_disponible(self):
        with self.assertRaises(ImproperlyConfigured):
            validar_configuracion()

    @override_settings(
        DEBUG=True, NUCLEO_ADAPTADOR="stub", PEDIDOS_COBRO_HABILITADO=False
    )
    def test_stub_con_credenciales_no_arranca(self):
        for caso in (
            {"PEY_API_KEY": "llave", "PEY_ADAPTADOR": "desarrollo"},
            {"PEY_API_KEY": "", "PEY_ADAPTADOR": "produccion"},
        ):
            with self.subTest(caso=caso), override_settings(**caso):
                with self.assertRaises(ImproperlyConfigured):
                    validar_configuracion()

    @override_settings(
        DEBUG=True,
        NUCLEO_ADAPTADOR="stub",
        PEDIDOS_COBRO_HABILITADO=False,
        PEY_API_KEY="",
        PEY_ADAPTADOR="",
    )
    def test_stub_sin_credenciales_arranca(self):
        validar_configuracion()
