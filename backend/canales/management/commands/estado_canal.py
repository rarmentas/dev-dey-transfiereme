from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from canales.models import LatidoCanal, MensajeEntrante, SalidaCanal


class Command(BaseCommand):
    help = "Muestra el estado del trabajador del canal."

    def add_arguments(self, parser):
        parser.add_argument("--max-edad", type=int, default=30)
        parser.add_argument("--mensajes", type=int, default=0)

    def handle(self, *args, **opciones):
        latido = LatidoCanal.objects.filter(pk="procesar_canal").first()
        edad = (
            (timezone.now() - latido.ultimo_ciclo).total_seconds() if latido else None
        )
        self.stdout.write(f"Edad del latido: {edad}")
        pendientes = MensajeEntrante.objects.filter(
            estado__in=["pendiente", "reintentable"]
        ).order_by("recibido_en")
        antiguo = pendientes.values_list("recibido_en", flat=True).first()
        self.stdout.write(f"Pendientes: {pendientes.count()}; más antiguo: {antiguo}")
        inciertas = SalidaCanal.objects.filter(estado="incierta").count()
        self.stdout.write(f"Salidas inciertas: {inciertas}")
        for identidad in MensajeEntrante.objects.order_by("-recibido_en").values_list(
            "id", flat=True
        )[: max(0, opciones["mensajes"])]:
            self.stdout.write(str(identidad))
        if edad is None or edad > opciones["max_edad"]:
            raise CommandError("Latido ausente o vencido.")
