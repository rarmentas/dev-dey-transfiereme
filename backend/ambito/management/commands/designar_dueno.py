"""Designa o revoca al dueño de un comercio."""

import logging

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--correo", required=True)
        parser.add_argument("--quitar", action="store_true")

    def handle(self, *args, **options):
        usuario = User.objects.filter(email__iexact=options["correo"]).first()
        membresia = getattr(usuario, "membresia", None) if usuario else None
        if not membresia:
            raise CommandError("No hay membresía para ese correo.")
        membresia.es_dueno = not options["quitar"]
        membresia.save(update_fields=["es_dueno"])
        logger.warning(
            "dueño actualizado usuario_id=%s comercio_id=%s valor=%s",
            usuario.pk,
            membresia.comercio_id,
            membresia.es_dueno,
        )
