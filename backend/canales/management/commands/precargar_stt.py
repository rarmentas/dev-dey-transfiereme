from django.core.management.base import BaseCommand

from canales.stt import FasterWhisperTranscriptor


class Command(BaseCommand):
    help = "Descarga y carga el modelo STT local."

    def handle(self, *args, **opciones):
        FasterWhisperTranscriptor().precargar()
