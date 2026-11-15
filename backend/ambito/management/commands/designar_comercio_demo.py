"""Designa o retira el comercio de demostración."""

import logging
import sys

from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from ambito.models import Comercio
from ambito.cuenta import cuenta_por_defecto

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    def add_arguments(self, parser):
        grupo = parser.add_mutually_exclusive_group(required=True)
        grupo.add_argument("--comercio", type=int)
        grupo.add_argument("--estado", action="store_true")
        parser.add_argument("--quitar", action="store_true")
        parser.add_argument("--si", action="store_true")

    def handle(self, *args, **options):
        if options["estado"]:
            comercio = Comercio.objects.filter(es_demo=True).first()
            self.stdout.write(
                f"Demo: {comercio.pk} {comercio.nombre}" if comercio else "Sin demo"
            )
            cuenta = cuenta_por_defecto(comercio) if comercio else None
            destino = cuenta.pey_bank_account_id if cuenta else ""
            self.stdout.write(
                f"Cuenta seleccionada: ...{destino[-4:]}"
                if destino
                else "Sin cuenta seleccionada"
            )
            return
        comercio = Comercio.objects.filter(pk=options["comercio"]).first()
        if not comercio:
            raise CommandError("Comercio inexistente.")
        quitar = options["quitar"]
        self.stdout.write(
            f"{'Quitar' if quitar else 'Designar'}: {comercio.pk} {comercio.nombre}"
        )
        if not options["si"]:
            if not sys.stdin.isatty():
                raise CommandError("Se requiere confirmación interactiva o --si.")
            if input("Teclee el id del comercio: ").strip() != str(comercio.pk):
                raise CommandError("Confirmación incorrecta.")
        from pedidos.servicios.intentos import plaza_ocupada

        try:
            with transaction.atomic():
                comercio = Comercio.objects.select_for_update().get(pk=comercio.pk)
                if comercio.es_demo == (not quitar):
                    self.stdout.write("Sin cambios.")
                    return
                if not quitar and Comercio.objects.filter(es_demo=True).exists():
                    raise CommandError("Quita el demo actual con --quitar.")
                if plaza_ocupada(comercio):
                    raise CommandError("El comercio tiene una plaza ocupada.")
                comercio.es_demo = not quitar
                comercio.save(update_fields=["es_demo"])
        except IntegrityError as exc:
            raise CommandError("Quita el demo actual con --quitar.") from exc
        logger.warning(
            "comercio demo actualizado comercio_id=%s es_demo=%s",
            comercio.pk,
            comercio.es_demo,
        )
