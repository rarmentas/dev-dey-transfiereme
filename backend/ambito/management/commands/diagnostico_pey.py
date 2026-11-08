"""Lee el gate de pey. Nunca imprime la llave ni el secreto."""

import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ambito.cuenta_sync import sincronizar_codi_status
from ambito.management.commands.registrar_cuenta_pey import _comercio_de_correo
from pey.cuentas import consultar_cuenta
from pey.seleccion import modo_adaptador
from pey.tipos import ErrorPey


class Command(BaseCommand):
    help = "Muestra el modo de pey y el codiStatus, sin imprimir secretos."

    def add_arguments(self, parser):
        parser.add_argument("--correo", required=True)

    def handle(self, *args, **options):
        try:
            modo = modo_adaptador()
        except Exception as exc:
            raise CommandError(str(exc)) from exc
        comercio = _comercio_de_correo(options["correo"])
        base = (
            getattr(settings, "WEBHOOK_BASE_URL", "")
            or os.environ.get("WEBHOOK_BASE_URL", "")
        ).rstrip("/")
        webhook = f"{base}/api/webhooks/pey/" if base else "(WEBHOOK_BASE_URL no configurada)"
        identificador = (comercio.pey_bank_account_id or "").strip()
        lineas = [
            f"modo: {modo}",
            f"PEY_API_KEY: {_si_no(settings.PEY_API_KEY)}",
            f"PEY_WEBHOOK_SECRET: {_si_no(settings.PEY_WEBHOOK_SECRET)}",
            f"webhook: {webhook}",
            f"pey_bank_account_id: {identificador or '(vacío)'}",
            f"pey_codi_status: {comercio.pey_codi_status}",
        ]
        if modo == "produccion" and identificador:
            try:
                cuenta = consultar_cuenta(identificador)
            except ErrorPey as exc:
                raise CommandError(
                    f"pey no consultó la cuenta tipo={exc.tipo} request_id={exc.request_id}"
                ) from exc
            sincronizar_codi_status(comercio)
            comercio.refresh_from_db()
            lineas.append(f"codiStatus: {cuenta.codi_status}")
            lineas.append(f"pey_codi_status: {comercio.pey_codi_status}")
        self.stdout.write("\n".join(lineas))


def _si_no(valor: str) -> str:
    return "sí" if (valor or "").strip() else "no"
