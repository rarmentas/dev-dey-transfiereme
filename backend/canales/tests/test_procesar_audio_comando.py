"""Comandos y mantenimiento del worker STT."""

import os
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from canales import audio
from canales.management.commands.procesar_audio import Detencion
from canales.models import LatidoCanal


@override_settings(STT_HABILITADO=True)
class ComandoAudioTests(SimpleTestCase):
    def test_una_vez_precarga_y_ejecuta_un_ciclo(self):
        with (
            patch(
                "canales.management.commands.procesar_audio.shutil.which",
                return_value="/bin/x",
            ),
            patch(
                "canales.management.commands.procesar_audio.barrer_temporales"
            ) as barrer,
            patch(
                "canales.management.commands.procesar_audio.FasterWhisperTranscriptor"
            ) as clase,
            patch("canales.management.commands.procesar_audio.ciclo") as ciclo,
        ):
            call_command("procesar_audio", una_vez=True)
        barrer.assert_called_once()
        clase.return_value.precargar.assert_called_once()
        ciclo.assert_called_once_with(clase.return_value)

    def test_max_ciclos(self):
        with (
            patch(
                "canales.management.commands.procesar_audio.shutil.which",
                return_value="x",
            ),
            patch("canales.management.commands.procesar_audio.barrer_temporales"),
            patch(
                "canales.management.commands.procesar_audio.FasterWhisperTranscriptor"
            ),
            patch("canales.management.commands.procesar_audio.ciclo") as ciclo,
        ):
            call_command("procesar_audio", max_ciclos=3, intervalo=0)
        self.assertEqual(ciclo.call_count, 3)

    def test_falta_ffmpeg_o_ffprobe_falla_antes_de_precargar(self):
        for presente in ("ffmpeg", "ffprobe"):
            with self.subTest(presente=presente):
                with (
                    patch(
                        "canales.management.commands.procesar_audio.shutil.which",
                        side_effect=lambda nombre, permitido=presente: (
                            "x" if nombre == permitido else None
                        ),
                    ),
                    patch(
                        "canales.management.commands.procesar_audio.FasterWhisperTranscriptor"
                    ) as clase,
                ):
                    with self.assertRaises(CommandError):
                        call_command("procesar_audio", una_vez=True)
                    clase.assert_not_called()

    def test_sigterm_detiene_tras_ciclo_actual(self):
        control = Detencion()
        with (
            patch(
                "canales.management.commands.procesar_audio.Detencion",
                return_value=control,
            ),
            patch(
                "canales.management.commands.procesar_audio.shutil.which",
                return_value="x",
            ),
            patch("canales.management.commands.procesar_audio.barrer_temporales"),
            patch(
                "canales.management.commands.procesar_audio.FasterWhisperTranscriptor"
            ),
            patch(
                "canales.management.commands.procesar_audio.ciclo",
                side_effect=lambda _: control.detener(),
            ) as ciclo,
        ):
            call_command("procesar_audio", intervalo=0)
        self.assertEqual(ciclo.call_count, 1)

    def test_precargar_stt(self):
        with patch(
            "canales.management.commands.precargar_stt.FasterWhisperTranscriptor"
        ) as clase:
            call_command("precargar_stt")
        clase.return_value.precargar.assert_called_once()

    def test_barrido_solo_directorios_stt_antiguos(self):
        with tempfile.TemporaryDirectory() as carpeta:
            antiguo = Path(carpeta) / "stt-viejo"
            reciente = Path(carpeta) / "stt-nuevo"
            ajeno = Path(carpeta) / "otro"
            for ruta in (antiguo, reciente, ajeno):
                ruta.mkdir()
            pasado = time.time() - 86401
            os.utime(antiguo, (pasado, pasado))
            os.utime(ajeno, (pasado, pasado))
            with patch("canales.audio.tempfile.gettempdir", return_value=carpeta):
                audio.barrer_temporales()
            self.assertFalse(antiguo.exists())
            self.assertTrue(reciente.exists())
            self.assertTrue(ajeno.exists())


class EstadoAudioTests(TestCase):
    def test_estado_proceso_seleccionado(self):
        LatidoCanal.objects.create(
            proceso="procesar_audio", ultimo_ciclo=timezone.now()
        )
        call_command("estado_canal", proceso="procesar_audio")
        with self.assertRaises(CommandError):
            call_command("estado_canal", proceso="procesar_canal")
