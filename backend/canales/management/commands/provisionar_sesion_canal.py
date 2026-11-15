from django.core.management.base import BaseCommand, CommandError

from ambito.models import Comercio
from canales.models import SesionCanal


class Command(BaseCommand):
    help = "Provisiona una sesión de canal."

    def add_arguments(self, parser):
        parser.add_argument("--instancia", required=True)
        parser.add_argument("--sesion", required=True)
        parser.add_argument("--comercio-id", required=True)
        parser.add_argument("--desactivar", action="store_true")

    def handle(self, *args, **opciones):
        comercio = Comercio.objects.filter(pk=opciones["comercio_id"]).first()
        if not comercio:
            raise CommandError("Comercio inexistente.")
        sesion, creada = SesionCanal.objects.get_or_create(
            instancia_id=opciones["instancia"],
            sesion_id=opciones["sesion"],
            defaults={"comercio": comercio},
        )
        if not creada and sesion.comercio_id != comercio.pk:
            raise CommandError("La sesión pertenece a otro comercio.")
        sesion.estado = "inactiva" if opciones["desactivar"] else "activa"
        sesion.save(update_fields=["estado"])
        self.stdout.write(str(sesion.pk))
