import shutil
import signal
import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from canales.audio import barrer_temporales, ciclo
from canales.stt import FasterWhisperTranscriptor


class Detencion:
    def __init__(self):
        self.detenido = False

    def detener(self, *_args):
        self.detenido = True


class Command(BaseCommand):
    help = "Procesa la cola local de audio."

    def add_arguments(self, parser):
        parser.add_argument("--una-vez", action="store_true")
        parser.add_argument("--intervalo", type=float, default=1.0)
        parser.add_argument("--max-ciclos", type=int)

    def handle(self, *args, **opciones):
        if not settings.STT_HABILITADO:
            raise CommandError("STT está deshabilitado.")
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            raise CommandError("Se requieren ffmpeg y ffprobe.")
        barrer_temporales()
        transcriptor = FasterWhisperTranscriptor()
        transcriptor.precargar()
        control = Detencion()
        anterior = signal.signal(signal.SIGTERM, control.detener)
        try:
            cantidad = 0
            while not control.detenido:
                ciclo(transcriptor)
                cantidad += 1
                if opciones["una_vez"] or (
                    opciones["max_ciclos"] and cantidad >= opciones["max_ciclos"]
                ):
                    break
                time.sleep(max(0, opciones["intervalo"]))
        finally:
            signal.signal(signal.SIGTERM, anterior)
