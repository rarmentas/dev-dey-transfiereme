"""Resuelve un registro incierto con evidencia de pey."""

import re

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from ambito.candados import bloquear_comercio, bloquear_cuenta
from ambito.models import CuentaCobro
from pey.cuentas import consultar_cuenta
from pey.tipos import ErrorPey


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--cuenta", required=True)
        parser.add_argument("--pey-id", required=True)

    def handle(self, *args, **options):
        ident = options["pey_id"]
        if not re.fullmatch(r"[0-9A-HJKMNP-TV-Z]{26}", ident):
            raise CommandError("ID pey inválido.")
        try:
            cuenta = CuentaCobro.objects.get(pk=options["cuenta"])
            if cuenta.registro_estado != "incierto":
                raise CommandError("La cuenta no está incierta.")
            version = cuenta.version
            remota = consultar_cuenta(ident)
        except (CuentaCobro.DoesNotExist, ValidationError, ValueError, ErrorPey):
            raise CommandError("No se pudo consultar la cuenta.") from None
        if remota.id != ident or remota.clabe != cuenta.clabe:
            raise CommandError("La cuenta consultada no coincide.")
        try:
            with transaction.atomic():
                bloquear_comercio(cuenta.comercio)
                cuenta = bloquear_cuenta(cuenta)
                if cuenta.version != version or cuenta.registro_estado != "incierto":
                    raise CommandError("La cuenta cambió durante la consulta.")
                CuentaCobro.objects.filter(pk=cuenta.pk).update(
                    registro_estado="registrado",
                    pey_bank_account_id=ident,
                    codi_status_crudo=remota.codi_status,
                    codi_status=(
                        "active" if remota.codi_status == "ACTIVE" else "pending"
                    ),
                    sincronizada_en=timezone.now(),
                    ultimo_error="",
                    version=F("version") + 1,
                )
                cuenta.operaciones.filter(tipo="registro", estado="incierta").update(
                    estado="aplicada",
                    terminado_en=timezone.now(),
                    pey_bank_account_id_obtenido=ident,
                )
        except IntegrityError:
            raise CommandError(
                "No se pudo enlazar la cuenta: ID ya asignado."
            ) from None
        self.stdout.write("Cuenta enlazada.")
