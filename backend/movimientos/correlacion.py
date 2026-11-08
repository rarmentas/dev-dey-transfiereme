"""Aplica un aviso de pago al cobro persistido. Sin HTTP y sin llamar a pey."""

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction

from movimientos.exceptions import AvisoInvalido, AvisoSinCobro
from movimientos.models import Cobro, Movimiento

TIPO_QR = "codi.qr.payment_received"
TIPO_PN = "codi.pn.payment_received"

_CANALES_QR = (
    Movimiento.Canal.QR_GENERAL,
    Movimiento.Canal.QR_VENTA,
)


@dataclass(frozen=True)
class AvisoPago:
    tipo: str
    monto: Decimal
    transaction_id: str
    codi_qr_id: str | None
    concepto: str = ""


def aplicar_aviso(aviso: AvisoPago, *, origen: Movimiento.Origen) -> Movimiento:
    with transaction.atomic():
        if aviso.tipo == TIPO_QR:
            return _aplicar_qr(aviso, origen)
        if aviso.tipo == TIPO_PN:
            return _aplicar_pn(aviso, origen)
        raise AvisoInvalido(f"Tipo de aviso desconocido: {aviso.tipo}.")


def _aplicar_qr(aviso: AvisoPago, origen: Movimiento.Origen) -> Movimiento:
    cobro = _cobro_por_qr(aviso.codi_qr_id)
    if cobro.canal == Movimiento.Canal.QR_GENERAL:
        return _crear_movimiento_de_qr_general(cobro, aviso, origen)
    return _marcar_ligado_pagado(cobro, aviso.transaction_id)


def _aplicar_pn(aviso: AvisoPago, origen: Movimiento.Origen) -> Movimiento:
    cobro = _cobro_por_notificacion(aviso.transaction_id)
    return _marcar_ligado_pagado(cobro, aviso.transaction_id)


def _cobro_por_qr(codi_qr_id: str | None) -> Cobro:
    if not codi_qr_id:
        raise AvisoSinCobro("El aviso de QR no trae codi_qr_id.")
    try:
        return Cobro.objects.select_for_update().get(
            pey_qr_id=codi_qr_id,
            canal__in=_CANALES_QR,
        )
    except Cobro.DoesNotExist:
        raise AvisoSinCobro("No hay cobro de QR con ese pey_qr_id.") from None


def _cobro_por_notificacion(transaction_id: str) -> Cobro:
    if not transaction_id:
        raise AvisoSinCobro("El aviso de notificación no trae transaction_id.")
    try:
        return Cobro.objects.select_for_update().get(
            pey_transaction_id=transaction_id,
            canal=Movimiento.Canal.NOTIFICACION,
        )
    except Cobro.DoesNotExist:
        raise AvisoSinCobro(
            "No hay cobro de notificación con ese pey_transaction_id."
        ) from None


def _crear_movimiento_de_qr_general(
    cobro: Cobro,
    aviso: AvisoPago,
    origen: Movimiento.Origen,
) -> Movimiento:
    # El comercio y el canal salen del cobro persistido, nunca del aviso.
    if cobro.canal != Movimiento.Canal.QR_GENERAL:
        raise ValueError(
            "El canal del movimiento tiene que coincidir con el del cobro."
        )
    return Movimiento.objects.create(
        comercio=cobro.comercio,
        cobro=cobro,
        canal=cobro.canal,
        monto=aviso.monto,
        concepto=cobro.concepto,
        estado=Movimiento.Estado.PAGADO,
        origen=origen,
        pey_transaction_id=aviso.transaction_id,
    )


def _marcar_ligado_pagado(cobro: Cobro, transaction_id: str) -> Movimiento:
    # El monto del aviso no se compara con el del cobro: producto no lo ha pedido.
    movimiento = _movimiento_ligado(cobro)
    if (
        movimiento.canal != cobro.canal
        or movimiento.comercio_id != cobro.comercio_id
    ):
        raise ValueError(
            "El canal y el comercio del movimiento tienen que ser los del cobro."
        )
    movimiento.pey_transaction_id = transaction_id
    # Si está vencido, cambiar_estado propaga TransicionInvalida y no queda pagado.
    movimiento.cambiar_estado(Movimiento.Estado.PAGADO)
    movimiento.save(update_fields=["pey_transaction_id", "actualizado_en"])
    return movimiento


def _movimiento_ligado(cobro: Cobro) -> Movimiento:
    """El pendiente del cobro, o el ligado si ya no está pendiente.

    Así un vencido llega a cambiar_estado y se rechaza, en vez de parecer
    que el cobro no existía.
    """
    ligados = cobro.movimientos.select_for_update().order_by("pk")
    pendiente = ligados.filter(estado=Movimiento.Estado.PENDIENTE).first()
    if pendiente is not None:
        return pendiente
    ligado = ligados.first()
    if ligado is None:
        raise AvisoSinCobro("No hay movimiento ligado a este cobro.")
    return ligado
