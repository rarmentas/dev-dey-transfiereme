"""Sincroniza el estado de cuenta en pey vía el adaptador inyectado."""

import logging

from django.utils import timezone

from ambito.models import Comercio
from integracion.pey.fabrica import obtener_adaptador_pey
from integracion.pey.puerto import CODI_STATUS_ACTIVE
from pey.tipos import ErrorPey

logger = logging.getLogger(__name__)


def sincronizar_codi_status(comercio: Comercio) -> Comercio:
    """Actualiza el estado guardado. Un fallo de pey no se propaga."""
    comercio, _error = sincronizar_codi_status_con_detalle(comercio)
    return comercio


def sincronizar_codi_status_con_detalle(
    comercio: Comercio,
) -> tuple[Comercio, ErrorPey | None]:
    try:
        resultado = obtener_adaptador_pey().consultar_cuenta_por_clabe(comercio)
    except ErrorPey as exc:
        if exc.tipo == "BANK_ACCOUNT_NOT_FOUND":
            comercio.pey_bank_account_id = ""
            comercio.pey_codi_status = Comercio.PeyCodiStatus.PENDING
            comercio.pey_codi_status_actualizado_en = timezone.now()
            comercio.save(
                update_fields=[
                    "pey_bank_account_id",
                    "pey_codi_status",
                    "pey_codi_status_actualizado_en",
                ]
            )
            return comercio, exc
        logger.warning(
            "pey no sincronizó la cuenta tipo=%s request_id=%s comercio_id=%s",
            exc.tipo,
            exc.request_id,
            comercio.pk,
        )
        return comercio, exc
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
    return comercio, None
