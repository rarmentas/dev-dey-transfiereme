import signal
import time

from django.core.management.base import BaseCommand

from canales.worker import ciclo


class Command(BaseCommand):
    help = "Procesa la cola del canal."

    def add_arguments(self, parser):
        parser.add_argument("--una-vez", action="store_true")
        parser.add_argument("--intervalo", type=float, default=1.0)
        parser.add_argument("--max-ciclos", type=int)

    def handle(self, *args, **opciones):
        detenido = False

        def detener(*_args):
            nonlocal detenido
            detenido = True

        anterior = signal.signal(signal.SIGTERM, detener)
        try:
            cantidad = 0
            while not detenido:
                ciclo()
                cantidad += 1
                if opciones["una_vez"] or (
                    opciones["max_ciclos"] and cantidad >= opciones["max_ciclos"]
                ):
                    break
                time.sleep(max(0, opciones["intervalo"]))
        finally:
            signal.signal(signal.SIGTERM, anterior)
