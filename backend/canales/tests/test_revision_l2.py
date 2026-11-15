"""Regresiones de la revisión de canales."""

import io
import json
import os
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings

from canales.parseo import parsear_renglones
from canales.waha import AdaptadorWaha


class ParseoRevisionTests(SimpleTestCase):
    def test_b1_unidades_y_cantidades_ambiguas(self):
        casos = [
            ("1 leche", "leche", "1", None),
            ("2 limones", "limones", "2", None),
            ("5 galletas", "galletas", "5", None),
            ("2 latas de atún", "latas de atún", "2", None),
            ("2 gramos de queso", "gramos de queso", "2", None),
            ("2 gr de sal", "sal", "2", "gr"),
            ("2kg de arroz", "arroz", "2", "kg"),
            ("2 l de leche", "leche", "2", "l"),
            ("12", "12", None, None),
            ("1.2345 kg de arroz", "1.2345 kg de arroz", None, None),
            ("12345 tortillas", "12345 tortillas", None, None),
            ("0 kg de arroz", "0 kg de arroz", None, None),
        ]
        for texto, nombre, cantidad, unidad in casos:
            with self.subTest(texto=texto):
                renglon = parsear_renglones(texto)[0]
                self.assertEqual(renglon.texto_solicitado, nombre)
                self.assertEqual(
                    str(renglon.cantidad_solicitada)
                    if renglon.cantidad_solicitada is not None
                    else None,
                    cantidad,
                )
                self.assertEqual(renglon.unidad_solicitada, unidad)

    @override_settings(WAHA_BASE_URL="http://localhost:3000", WAHA_API_KEY="prueba")
    def test_i7_formatos_de_identidad_waha(self):
        ruta = Path(__file__).parent / "fixtures" / "respuestas_waha.json"
        respuestas = json.loads(ruta.read_text())
        for respuesta in respuestas:
            with self.subTest(respuesta=respuesta):
                stream = io.BytesIO(json.dumps(respuesta).encode())
                opener = Mock()
                opener.open.return_value = stream
                with patch("canales.waha.request.build_opener", return_value=opener):
                    self.assertEqual(AdaptadorWaha().enviar_texto("s", "c", "t"), "abc")

    def test_i3_instancia_vacia_usa_waha(self):
        entorno = {**os.environ, "WAHA_INSTANCIA": ""}
        resultado = subprocess.run(
            [
                os.sys.executable,
                "-c",
                "from config.settings import WAHA_INSTANCIA; print(WAHA_INSTANCIA)",
            ],
            env=entorno,
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(resultado.stdout.strip(), "waha")
