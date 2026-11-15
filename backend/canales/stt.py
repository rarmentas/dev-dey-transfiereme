"""Puerto de transcripción local."""

import time
from typing import Protocol

from django.conf import settings


class SttTimeout(Exception):
    pass


class Transcriptor(Protocol):
    def precargar(self): ...

    def transcribir(self, audio_float32, deadline): ...


class FasterWhisperTranscriptor:
    def __init__(self):
        self.modelo = None

    def precargar(self):
        if self.modelo is None:
            from faster_whisper import WhisperModel

            self.modelo = WhisperModel(
                settings.STT_MODELO,
                device="cpu",
                compute_type="int8",
                cpu_threads=settings.STT_CPU_THREADS,
            )

    def transcribir(self, audio_float32, deadline):
        import numpy

        self.precargar()
        if time.monotonic() >= deadline:
            raise SttTimeout
        segmentos, _ = self.modelo.transcribe(
            numpy.asarray(audio_float32, dtype=numpy.float32),
            language="es",
            beam_size=1,
            vad_filter=True,
        )
        partes = []
        for segmento in segmentos:
            if time.monotonic() >= deadline:
                raise SttTimeout
            partes.append(segmento.text)
        return " ".join(partes).strip()
