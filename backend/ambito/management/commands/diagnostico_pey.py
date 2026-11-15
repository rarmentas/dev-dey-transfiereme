"""Diagnóstico de cuentas sin exponer datos sensibles."""

from django.core.management.base import BaseCommand

from ambito.cuenta import cuenta_por_defecto
from ambito.cuenta_pey_servicio import enmascarar_clabe, sufijo_ulid
from ambito.management.commands.registrar_cuenta_pey import _comercio_de_correo
from ambito.operaciones_cuenta import ErrorOperacion, sincronizar
from pey.seleccion import modo_adaptador


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--correo", required=True)

    def handle(self, *args, **options):
        comercio = _comercio_de_correo(options["correo"])
        cuenta = cuenta_por_defecto(comercio)
        if cuenta and modo_adaptador() == "produccion":
            try:
                sincronizar(cuenta)
            except ErrorOperacion:
                pass
        for cuenta in comercio.cuentas.all():
            self.stdout.write(
                f"{enmascarar_clabe(cuenta.clabe)} "
                f"id={sufijo_ulid(cuenta.pey_bank_account_id)} "
                f"estado={cuenta.codi_status} registro={cuenta.registro_estado} "
                f"error={cuenta.ultimo_error}"
            )
