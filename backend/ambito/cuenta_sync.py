"""Sincroniza el estado de cuenta en pey vía el adaptador inyectado."""

from django.utils import timezone

from ambito.models import Comercio
from integracion.pey.fabrica import obtener_adaptador_pey
from integracion.pey.puerto import CODI_STATUS_ACTIVE


def sincronizar_codi_status(comercio: Comercio) -> Comercio:
    resultado = obtener_adaptador_pey().consultar_cuenta_por_clabe(comercio)
    if resultado.codi_status == CODI_STATUS_ACTIVE:
        comercio.pey_codi_status = Comercio.PeyCodiStatus.ACTIVE
        comercio.pey_bank_account_id = resultado.bank_account_id
    else:
        comercio.pey_codi_status = Comercio.PeyCodiStatus.PENDING
        # PENDING con id (producción) no borra el registro. Sin id, se limpia.
        if resultado.bank_account_id:
            comercio.pey_bank_account_id = resultado.bank_account_id
        else:
            comercio.pey_bank_account_id = ""
    comercio.pey_codi_status_actualizado_en = timezone.now()
    comercio.save(
        update_fields=[
            "pey_codi_status",
            "pey_bank_account_id",
            "pey_codi_status_actualizado_en",
        ]
    )
    return comercio
