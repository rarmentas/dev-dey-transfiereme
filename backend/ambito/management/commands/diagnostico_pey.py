"""Lee el gate de pey. Nunca imprime la llave ni el secreto."""

import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ambito.cuenta_sync import sincronizar_codi_status_con_detalle
from ambito.management.commands.registrar_cuenta_pey import (
    _comercio_de_correo,
    enmascarar_clabe,
)
from pey.seleccion import modo_adaptador


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
            f"clabe: {enmascarar_clabe(comercio.clabe)}",
            f"pey_bank_account_id: {identificador or '(vacío)'}",
        ]
        if modo == "produccion" and identificador:
            comercio, error = sincronizar_codi_status_con_detalle(comercio)
            if error is not None:
                lineas.append(f"error: tipo={error.tipo} request_id={error.request_id}")
            else:
                lineas.append(f"codiStatus: {comercio.pey_codi_status}")
        lineas.append(f"pey_codi_status: {comercio.pey_codi_status}")
        lineas.append(f"pey_bank_account_id: {comercio.pey_bank_account_id or '(vacío)'}")
        self.stdout.write("\n".join(lineas))


def _si_no(valor: str) -> str:
    return "sí" if (valor or "").strip() else "no"
