"""Alta del QR general de un comercio vía el puerto pey (sin HTTP aquí)."""

import logging
from dataclasses import dataclass
from decimal import Decimal

from django.db import IntegrityError, transaction

from ambito.exceptions import CuentaNoActiveError
from ambito.models import Comercio
from movimientos.cobro_qr import preparar_alta_qr_general
from movimientos.models import Cobro, Movimiento
from pey.produccion import AdaptadorProduccion
from pey.seleccion import obtener_puerto
from pey.tipos import QrCreado

logger = logging.getLogger(__name__)

_CONCEPTO_QR_GENERAL = "Transferencia"


@dataclass(frozen=True)
class ResultadoAltaQrGeneral:
    cobro: Cobro
    creado: bool


def alta_qr_general(comercio: Comercio) -> ResultadoAltaQrGeneral:
    preparar_alta_qr_general(comercio)
    puerto = obtener_puerto()
    # En producción se exige la cuenta antes de reutilizar un QR viejo.
    cuenta = _cuenta_de_produccion(puerto, comercio)
    ident = cuenta.get("bank_account_id", "")

    existente = _qr_general_de_comercio(comercio)
    if existente is not None and _se_reutiliza(puerto, existente, ident):
        return ResultadoAltaQrGeneral(cobro=existente, creado=False)

    qr = _pedir_qr(puerto, cuenta)
    if existente is not None:
        return _regenerar(existente, qr, ident)

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
                pey_bank_account_id=ident,
            )
            return ResultadoAltaQrGeneral(cobro=cobro, creado=True)
    except IntegrityError:
        existente = _qr_general_de_comercio(comercio)
        if existente is None:
            raise
        if _se_reutiliza(puerto, existente, ident):
            return ResultadoAltaQrGeneral(cobro=existente, creado=False)
        return _regenerar(existente, qr, ident)


def _cuenta_de_produccion(puerto: object, comercio: Comercio) -> dict[str, str]:
    if not isinstance(puerto, AdaptadorProduccion):
        return {}
    ident = (comercio.pey_bank_account_id or "").strip()
    if not ident:
        raise CuentaNoActiveError()
    return {"bank_account_id": ident}


def _se_reutiliza(puerto: object, cobro: Cobro, ident: str) -> bool:
    """En desarrollo se reutiliza siempre. En producción, solo si la cuenta coincide."""
    if not isinstance(puerto, AdaptadorProduccion):
        return True
    return cobro.pey_bank_account_id == ident


def _pedir_qr(puerto: object, cuenta: dict[str, str]) -> QrCreado:
    return puerto.crear_qr(
        monto=Decimal("0"),
        concepto="",
        expiracion_s=0,
        num_ref="0",
        **cuenta,
    )


def _regenerar(cobro: Cobro, qr: QrCreado, ident: str) -> ResultadoAltaQrGeneral:
    """Misma fila: el QR general es único por comercio y pey_qr_id es único."""
    cobro.pey_qr_id = qr.id
    cobro.qr_string = qr.qr_string
    cobro.pey_bank_account_id = ident
    cobro.save(update_fields=["pey_qr_id", "qr_string", "pey_bank_account_id"])
    logger.warning("QR general regenerado cobro_id=%s", cobro.pk)
    return ResultadoAltaQrGeneral(cobro=cobro, creado=False)


def _qr_general_de_comercio(comercio: Comercio) -> Cobro | None:
    return Cobro.objects.filter(
        comercio=comercio,
        canal=Movimiento.Canal.QR_GENERAL,
    ).first()
