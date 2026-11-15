"""Inspección y conversión limitada de audio."""

import array
import json
import subprocess
import sys
import wave

from django.conf import settings

from canales.media import ErrorAudio


def inspeccionar(ruta, timeout):
    try:
        with open(ruta, "rb") as archivo:
            cabecera = archivo.read(512).lstrip().lower()
        if cabecera.startswith((b"#extm3u", b"#extinf", b"ffconcat")) or any(
            token in cabecera
            for token in (b"concat:", b"file://", b"http://", b"https://")
        ):
            raise ErrorAudio("formato")
        resultado = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-protocol_whitelist",
                "file,pipe",
                "-show_entries",
                "format=format_name,duration",
                "-of",
                "json",
                str(ruta),
            ],
            capture_output=True,
            check=True,
            timeout=timeout,
        )
        formato = json.loads(resultado.stdout)["format"]
        tokens = set(formato["format_name"].split(","))
        permitidos = {
            "ogg",
            "opus",
            "mp3",
            "mp4",
            "m4a",
            "mov",
            "wav",
            "webm",
            "matroska",
            "3gp",
            "3g2",
            "mj2",
        }
        if not tokens or not tokens <= permitidos:
            raise ErrorAudio("formato")
        duracion = float(formato["duration"])
        if not 0 < duracion <= settings.WHATSAPP_AUDIO_MAX_SEGUNDOS:
            raise ErrorAudio("demasiado_largo" if duracion > 90 else "vacio")
    except (
        subprocess.SubprocessError,
        OSError,
        ValueError,
        KeyError,
        TypeError,
    ) as exc:
        raise ErrorAudio("formato") from exc


def a_wav_16k(origen, destino, timeout):
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-nostdin",
                "-v",
                "error",
                "-protocol_whitelist",
                "file,pipe",
                "-i",
                str(origen),
                "-t",
                str(settings.WHATSAPP_AUDIO_MAX_SEGUNDOS + 1),
                "-ac",
                "1",
                "-ar",
                "16000",
                "-acodec",
                "pcm_s16le",
                "-y",
                str(destino),
            ],
            capture_output=True,
            check=True,
            timeout=timeout,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        raise ErrorAudio("formato") from exc


def validar_wav(ruta):
    try:
        with wave.open(str(ruta), "rb") as archivo:
            frames = archivo.getnframes()
            if (
                archivo.getnchannels() != 1
                or archivo.getframerate() != 16000
                or archivo.getsampwidth() != 2
                or archivo.getcomptype() != "NONE"
                or frames < 1
                or frames > 16000 * settings.WHATSAPP_AUDIO_MAX_SEGUNDOS
            ):
                raise ErrorAudio("wav_invalido")
            datos = archivo.readframes(frames)
            if len(datos) != frames * 2:
                raise ErrorAudio("wav_invalido")
        muestras = array.array("h")
        muestras.frombytes(datos)
        if sys.byteorder != "little":
            muestras.byteswap()
        return array.array("f", (muestra / 32768 for muestra in muestras))
    except (wave.Error, EOFError, OSError, ValueError) as exc:
        raise ErrorAudio("wav_invalido") from exc
