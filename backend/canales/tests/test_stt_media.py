"""Pruebas de audio del canal."""

import io
import tempfile
import wave
from pathlib import Path
from unittest.mock import Mock

from django.test import SimpleTestCase, override_settings

from canales import audio_conversion, media


class Respuesta:
    status = 200

    def __init__(self, datos=b"audio", headers=None):
        self.datos = io.BytesIO(datos)
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self, cantidad):
        return self.datos.read(cantidad)


@override_settings(WAHA_BASE_URL="http://waha:3000", WAHA_API_KEY="clave")
class MediaTests(SimpleTestCase):
    def test_origen_y_traversal(self):
        self.assertTrue(media.origen_permitido("http://waha:3000/api/files/a"))
        for url in [
            "http://otro:3000/api/files/a",
            "https://waha:3000/api/files/a",
            "http://waha:3001/api/files/a",
            "http://x@waha:3000/api/files/a",
            "http://waha:3000/api/files/a?q=1",
            "http://waha:3000/api/files/a#x",
            "http://waha:3000/api/files/%2e%2e/a",
        ]:
            with self.subTest(url=url):
                self.assertFalse(media.origen_permitido(url))

    @override_settings(WHATSAPP_AUDIO_MAX_BYTES=5)
    def test_limites_vacio_y_redirect(self):
        with tempfile.TemporaryDirectory() as carpeta:
            for respuesta, motivo in [
                (Respuesta(b"123456"), "demasiado_grande"),
                (Respuesta(b"1", {"Content-Length": "6"}), "demasiado_grande"),
                (Respuesta(b""), "vacio"),
            ]:
                with (
                    self.subTest(motivo=motivo),
                    self.assertRaises(media.ErrorAudio) as e,
                ):
                    media.descargar_acotado(
                        "http://waha:3000/api/files/a",
                        Path(carpeta) / "a",
                        1,
                        Mock(open=Mock(return_value=respuesta)),
                    )
                self.assertEqual(e.exception.motivo, motivo)
            respuesta = Respuesta()
            respuesta.status = 302
            opener = Mock(open=Mock(return_value=respuesta))
            with self.assertRaises(media.ErrorAudio) as e:
                media.descargar_acotado("http://waha:3000/api/files/a", "x", 1, opener)
            self.assertEqual(e.exception.motivo, "redireccion")
            self.assertEqual(opener.open.call_count, 1)

    def test_wav_real_y_cabecera_inesperada(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "a.wav"
            with wave.open(str(ruta), "wb") as wav:
                wav.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
                wav.writeframes(b"\x00\x00" * 160)
            self.assertEqual(len(audio_conversion.validar_wav(ruta)), 160)
            with wave.open(str(ruta), "wb") as wav:
                wav.setparams((2, 2, 16000, 0, "NONE", "not compressed"))
                wav.writeframes(b"\x00" * 4)
            with self.assertRaises(media.ErrorAudio) as e:
                audio_conversion.validar_wav(ruta)
            self.assertEqual(e.exception.motivo, "wav_invalido")

    @override_settings(WHATSAPP_AUDIO_MAX_BYTES=5_000_000)
    def test_streaming_corta_al_superar_cinco_megabytes(self):
        respuesta = Respuesta(b"a" * 5_000_001)
        respuesta.read = Mock(wraps=respuesta.read)
        with tempfile.TemporaryDirectory() as carpeta:
            with self.assertRaises(media.ErrorAudio) as error:
                media.descargar_acotado(
                    "http://waha:3000/api/files/a",
                    Path(carpeta) / "a",
                    1,
                    Mock(open=Mock(return_value=respuesta)),
                )
        self.assertEqual(error.exception.motivo, "demasiado_grande")
        self.assertGreater(respuesta.read.call_count, 1)

    def test_content_length_rechazado_antes_de_leer(self):
        respuesta = Respuesta(b"x", {"Content-Length": "5000001"})
        respuesta.read = Mock(wraps=respuesta.read)
        with self.assertRaises(media.ErrorAudio) as error:
            media.descargar_acotado(
                "http://waha:3000/api/files/a",
                "x",
                1,
                Mock(open=Mock(return_value=respuesta)),
            )
        self.assertEqual(error.exception.motivo, "demasiado_grande")
        respuesta.read.assert_not_called()

    def test_api_key_solo_al_origen_confiable(self):
        opener = Mock(open=Mock(return_value=Respuesta()))
        with tempfile.TemporaryDirectory() as carpeta:
            media.descargar_acotado(
                "http://waha:3000/api/files/a", Path(carpeta) / "a", 1, opener
            )
        self.assertEqual(opener.open.call_args.args[0].get_header("X-api-key"), "clave")
        opener.reset_mock()
        with self.assertRaises(media.ErrorAudio):
            media.descargar_acotado("http://ajeno/api/files/a", "x", 1, opener)
        opener.open.assert_not_called()

    def test_redirect_ajeno_no_se_sigue(self):
        respuesta = Respuesta(headers={"Location": "http://ajeno/api/files/a"})
        respuesta.status = 302
        opener = Mock(open=Mock(return_value=respuesta))
        with self.assertRaises(media.ErrorAudio) as error:
            media.descargar_acotado("http://waha:3000/api/files/a", "x", 1, opener)
        self.assertEqual(error.exception.motivo, "redireccion")
        self.assertEqual(opener.open.call_count, 1)

    def test_traversal_literal_y_codificado(self):
        for ruta in ("../a", "%2e%2e/a", "%2E/a"):
            with self.subTest(ruta=ruta):
                self.assertFalse(
                    media.origen_permitido(f"http://waha:3000/api/files/{ruta}")
                )
