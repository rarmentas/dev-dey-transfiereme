"""Registra en pey la CLABE ya guardada del comercio. Sin --confirmar no hay red."""

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from ambito.clabe import clabe_es_valida
from ambito.cuenta_pey_servicio import (
    CuentaPeyYaRegistrada,
    SinClabeGuardada,
    enmascarar_clabe,
    registrar_cuenta_en_pey,
)
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
        parser.add_argument("--reemplazar", action="store_true")

    def handle(self, *args, **options):
        self._exigir_produccion()
        comercio = _comercio_de_correo(options["correo"])
        clabe = (comercio.clabe or "").strip()
        if not clabe_es_valida(clabe):
            raise CommandError("El comercio no tiene una CLABE válida guardada.")
        if (comercio.pey_bank_account_id or "").strip() and not options["reemplazar"]:
            raise CommandError(
                "El comercio ya tiene cuenta en pey. Use --reemplazar para registrar otra."
            )
        nombre = options["nombre"].strip()
        alias = (options["alias"] or nombre).strip()
        entidad = options["entidad"]
        self.stdout.write(
            "\n".join(
                [
                    "POST /bank-account",
                    f"alias: {alias}",
                    f"name: {nombre}",
                    f"clabe: {enmascarar_clabe(clabe)}",
                    f"entity: {entidad}",
                ]
            )
        )
        if not options["confirmar"]:
            self.stdout.write("Sin --confirmar no se llama a pey.")
            return
        try:
            comercio, codi_status_pey = registrar_cuenta_en_pey(
                comercio.pk,
                nombre=nombre,
                entidad=entidad,
                alias=alias,
                reemplazar=options["reemplazar"],
            )
        except SinClabeGuardada as exc:
            raise CommandError("El comercio no tiene una CLABE válida guardada.") from exc
        except CuentaPeyYaRegistrada as exc:
            raise CommandError(
                "El comercio ya tiene cuenta en pey. Use --reemplazar para registrar otra."
            ) from exc
        except ParametroInvalido as exc:
            raise CommandError(str(exc)) from exc
        except ErrorPey as exc:
            raise CommandError(
                f"pey no registró la cuenta tipo={exc.tipo} request_id={exc.request_id}"
            ) from exc
        self.stdout.write(
            f"Cuenta registrada id={comercio.pey_bank_account_id} codiStatus={codi_status_pey}"
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
