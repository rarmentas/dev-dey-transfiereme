"""Registra una cuenta con confirmación explícita."""

import uuid

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from ambito.cuenta_pey_servicio import AdaptadorNoProduccion, enmascarar_clabe
from ambito.operaciones_cuenta import ErrorOperacion, registrar


def _comercio_de_correo(correo):
    usuario = User.objects.filter(email__iexact=correo).first()
    if not usuario:
        usuario = User.objects.filter(username__iexact=correo).first()
    membresia = getattr(usuario, "membresia", None) if usuario else None
    if not membresia:
        raise CommandError("No hay membresía para ese correo.")
    return membresia.comercio


class Command(BaseCommand):
    help = "Registra una cuenta de cobro en pey."

    def add_arguments(self, parser):
        parser.add_argument("--correo", required=True)
        parser.add_argument("--cuenta", required=True)
        parser.add_argument("--nombre", required=True)
        parser.add_argument("--entidad", required=True, choices=("PERSON", "BUSINESS"))
        parser.add_argument("--alias", default="")
        parser.add_argument("--confirmar", action="store_true")

    def handle(self, *args, **options):
        comercio = _comercio_de_correo(options["correo"])
        try:
            cuenta = comercio.cuentas.get(pk=options["cuenta"])
        except (ValueError, comercio.cuentas.model.DoesNotExist) as exc:
            raise CommandError("Cuenta no encontrada.") from exc
        self.stdout.write(f"CLABE: {enmascarar_clabe(cuenta.clabe)}")
        if not options["confirmar"]:
            self.stdout.write("Sin --confirmar no se llama a pey.")
            return
        try:
            cuenta, _ = registrar(
                cuenta, nombre=options["nombre"], entidad=options["entidad"],
                alias=options["alias"], clave=str(uuid.uuid4()), version=cuenta.version,
            )
        except (ErrorOperacion, AdaptadorNoProduccion) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(f"Registro: {cuenta.registro_estado}")
