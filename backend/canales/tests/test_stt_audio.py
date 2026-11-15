"""Pruebas de audio del canal."""

import tempfile
import wave
from pathlib import Path
from unittest.mock import Mock

from django.test import SimpleTestCase, override_settings

from canales import audio_conversion, media


@override_settings(WAHA_BASE_URL="http://waha:3000")
class LimitesAdicionalesTests(SimpleTestCase):
    def test_timeout_descarga_y_sin_segunda_peticion(self):
        opener = Mock()
        opener.open.side_effect = TimeoutError()
        with self.assertRaises(media.ErrorAudio) as error:
            media.descargar_acotado("http://waha:3000/api/files/a", "x", 1, opener)
        self.assertEqual(error.exception.motivo, "descarga")
        self.assertEqual(opener.open.call_count, 1)

    def test_duracion_real_mayor_a_90(self):
        import shutil

        if not shutil.which("ffprobe"):
            self.skipTest("ffprobe no disponible")
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "largo.wav"
            with wave.open(str(ruta), "wb") as wav:
                wav.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
                wav.writeframes(b"\x00\x00" * (16000 * 91))
            with self.assertRaises(media.ErrorAudio) as error:
                audio_conversion.inspeccionar(ruta, 10)
            self.assertEqual(error.exception.motivo, "demasiado_largo")

    def test_wav_con_chunk_adicional_valido(self):
        import struct

        from canales.tests.soporte_audio import escribir_wav

        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "audio.wav"
            escribir_wav(ruta)
            datos = ruta.read_bytes()
            chunk = b"JUNK" + struct.pack("<I", 4) + b"abcd"
            contenido = datos[12:36] + chunk + datos[36:]
            ruta.write_bytes(
                b"RIFF" + struct.pack("<I", len(contenido) + 4) + b"WAVE" + contenido
            )
            muestras = audio_conversion.validar_wav(ruta)
            self.assertEqual(len(muestras), 160)
            self.assertNotEqual(muestras[0], 0)

    def test_wav_parametros_inesperados_y_vacio(self):
        from canales.tests.soporte_audio import escribir_wav

        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "audio.wav"
            for cambios in (
                {"canales": 2},
                {"frecuencia": 8000},
                {"bytes_muestra": 1},
                {"frames": 0},
            ):
                with self.subTest(cambios=cambios):
                    escribir_wav(ruta, **cambios)
                    with self.assertRaises(media.ErrorAudio) as error:
                        audio_conversion.validar_wav(ruta)
                    self.assertEqual(error.exception.motivo, "wav_invalido")
