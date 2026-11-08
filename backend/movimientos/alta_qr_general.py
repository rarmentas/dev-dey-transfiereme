"""Alta del QR general de un comercio vía el puerto pey (sin HTTP aquí)."""

from dataclasses import dataclass
from decimal import Decimal

from django.db import IntegrityError, transaction

from ambito.models import Comercio
from movimientos.exceptions import CuentaInactivaParaCobro
from movimientos.models import Cobro, Movimiento
from pey.seleccion import obtener_puerto

_CONCEPTO_QR_GENERAL = "Transferencia"


@dataclass(frozen=True)
class ResultadoAltaQrGeneral:
    cobro: Cobro
    creado: bool


def alta_qr_general(comercio: Comercio) -> ResultadoAltaQrGeneral:
    puerto = obtener_puerto()
    if not puerto.cuenta_active(comercio):
        raise CuentaInactivaParaCobro

    existente = _qr_general_de_comercio(comercio)
    if existente is not None:
        return ResultadoAltaQrGeneral(cobro=existente, creado=False)

    qr = puerto.crear_qr(
        monto=Decimal("0"),
        concepto="",
        expiracion_s=0,
        num_ref="0",
    )

    try:
        with transaction.atomic():
            cobro = Cobro.objects.create(
                comercio=comercio,
                canal=Movimiento.Canal.QR_GENERAL,
                monto=Decimal("0"),
                concepto=_CONCEPTO_QR_GENERAL,
                vence_en=None,
                pey_qr_id=qr.id,
                qr_string=qr.qr_string,
            )
            return ResultadoAltaQrGeneral(cobro=cobro, creado=True)
    except IntegrityError:
        existente = _qr_general_de_comercio(comercio)
        if existente is None:
            raise
        return ResultadoAltaQrGeneral(cobro=existente, creado=False)


def _qr_general_de_comercio(comercio: Comercio) -> Cobro | None:
    return Cobro.objects.filter(
        comercio=comercio,
        canal=Movimiento.Canal.QR_GENERAL,
    ).first()
