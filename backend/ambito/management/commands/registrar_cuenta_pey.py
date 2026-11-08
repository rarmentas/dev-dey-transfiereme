"""Registra en pey la CLABE ya guardada del comercio. Sin --confirmar no hay red."""

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from ambito.clabe import clabe_es_valida
from ambito.models import Comercio
from pey.cuentas import registrar_cuenta
from pey.seleccion import modo_adaptador
from pey.tipos import ErrorPey, ParametroInvalido


class Command(BaseCommand):
    help = "Registra en pey la CLABE del comercio del vendedor. Sin --confirmar no llama."

    def add_arguments(self, parser):
        parser.add_argument("--correo", required=True)
        parser.add_argument("--nombre", required=True)
        parser.add_argument("--entidad", required=True, choices=("PERSON", "BUSINESS"))
        parser.add_argument("--alias", default="")
        parser.add_argument("--confirmar", action="store_true")

    def handle(self, *args, **options):
        self._exigir_produccion()
        comercio = _comercio_de_correo(options["correo"])
        clabe = (comercio.clabe or "").strip()
        if not clabe_es_valida(clabe):
            raise CommandError("El comercio no tiene una CLABE válida guardada.")
        nombre = options["nombre"].strip()
        alias = (options["alias"] or nombre).strip()
        entidad = options["entidad"]
        self.stdout.write(
            "\n".join(
                [
                    "POST /bank-account",
                    f"alias: {alias}",
                    f"name: {nombre}",
                    f"clabe: {clabe}",
                    f"entity: {entidad}",
                ]
            )
        )
        if not options["confirmar"]:
            self.stdout.write("Sin --confirmar no se llama a pey.")
            return
        try:
            cuenta = registrar_cuenta(
                alias=alias,
                nombre=nombre,
                clabe=clabe,
                entidad=entidad,
            )
        except ParametroInvalido as exc:
            raise CommandError(str(exc)) from exc
        except ErrorPey as exc:
            raise CommandError(
                f"pey no registró la cuenta tipo={exc.tipo} request_id={exc.request_id}"
            ) from exc
        if cuenta.codi_status == "ACTIVE":
            comercio.pey_codi_status = Comercio.PeyCodiStatus.ACTIVE
        else:
            comercio.pey_codi_status = Comercio.PeyCodiStatus.PENDING
        comercio.pey_bank_account_id = cuenta.id
        comercio.pey_codi_status_actualizado_en = timezone.now()
        comercio.save(
            update_fields=[
                "pey_bank_account_id",
                "pey_codi_status",
                "pey_codi_status_actualizado_en",
            ]
        )
        self.stdout.write(
            f"Cuenta registrada id={cuenta.id} codiStatus={cuenta.codi_status}"
        )

    def _exigir_produccion(self) -> None:
        try:
            modo = modo_adaptador()
        except Exception as exc:
            raise CommandError(str(exc)) from exc
        if modo != "produccion":
            raise CommandError("Este comando solo corre con PEY_ADAPTADOR=produccion.")


def _comercio_de_correo(correo: str):
    limpio = (correo or "").strip()
    if not limpio:
        raise CommandError("Indique el correo del vendedor.")
    usuario = (
        User.objects.select_related("membresia__comercio")
        .filter(email__iexact=limpio)
        .first()
    )
    if usuario is None:
        usuario = (
            User.objects.select_related("membresia__comercio")
            .filter(username__iexact=limpio)
            .first()
        )
    if usuario is None:
        raise CommandError("No hay un vendedor con ese correo.")
    membresia = getattr(usuario, "membresia", None)
    if membresia is None:
        raise CommandError("Ese vendedor no tiene comercio.")
    return membresia.comercio
