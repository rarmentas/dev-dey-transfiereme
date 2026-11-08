from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ambito.models import Comercio, Membresia

CORREO_DEMO = "vendedor@demo.mx"
COMERCIO_DEMO = "Comercio demo"


class Command(BaseCommand):
    help = "Crea el vendedor de desarrollo y su comercio, sin movimientos."

    def add_arguments(self, parser):
        parser.add_argument("--correo", default=CORREO_DEMO)
        parser.add_argument("--contraseña", required=True)
        parser.add_argument("--comercio", default=COMERCIO_DEMO)

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Este comando solo corre con DEBUG activo.")

        correo = options["correo"].strip().lower()
        nombre = options["comercio"].strip()
        if not correo or not nombre:
            raise CommandError("Indique correo y nombre de comercio.")

        with transaction.atomic():
            usuario, _creado = User.objects.get_or_create(
                username=correo,
                defaults={"email": correo},
            )
            usuario.email = correo
            usuario.set_password(options["contraseña"])
            usuario.save()

            membresia = getattr(usuario, "membresia", None)
            if membresia is None:
                comercio = _comercio_de_semilla(nombre)
                Membresia.objects.create(usuario=usuario, comercio=comercio)
            else:
                comercio = membresia.comercio
                if not comercio.semilla_active_dev and comercio.nombre != nombre:
                    raise CommandError(
                        "Ese correo ya pertenece a otro comercio. No se reasigna."
                    )
                comercio.nombre = nombre
                comercio.semilla_active_dev = True
                comercio.save(update_fields=["nombre", "semilla_active_dev"])

        self.stdout.write(
            f"Vendedor {correo} listo en «{comercio.nombre}». No se crearon movimientos."
        )


def _comercio_de_semilla(nombre: str) -> Comercio:
    comercio, _creado = Comercio.objects.get_or_create(
        nombre=nombre,
        defaults={"semilla_active_dev": True},
    )
    if not comercio.semilla_active_dev:
        raise CommandError(
            f"Ya existe el comercio «{nombre}» y no es de la semilla. Use otro nombre."
        )
    return comercio
