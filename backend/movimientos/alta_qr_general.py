"""Alta del QR general de un comercio vía el puerto pey (sin HTTP aquí)."""

from dataclasses import dataclass
from decimal import Decimal

from django.db import IntegrityError, transaction

from ambito.exceptions import CuentaNoActiveError
from ambito.models import Comercio
from movimientos.cobro_qr import preparar_alta_qr_general
from movimientos.models import Cobro, Movimiento
from pey.produccion import AdaptadorProduccion
from pey.seleccion import obtener_puerto

_CONCEPTO_QR_GENERAL = "Transferencia"


@dataclass(frozen=True)
class ResultadoAltaQrGeneral:
    cobro: Cobro
    creado: bool


def alta_qr_general(comercio: Comercio) -> ResultadoAltaQrGeneral:
    preparar_alta_qr_general(comercio)
    puerto = obtener_puerto()

    existente = _qr_general_de_comercio(comercio)
    if existente is not None:
        return ResultadoAltaQrGeneral(cobro=existente, creado=False)

    qr = puerto.crear_qr(
        monto=Decimal("0"),
        concepto="",
        expiracion_s=0,
        num_ref="0",
        **_cuenta_de_produccion(puerto, comercio),
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


def _cuenta_de_produccion(puerto: object, comercio: Comercio) -> dict[str, str]:
    if not isinstance(puerto, AdaptadorProduccion):
        return {}
    ident = (comercio.pey_bank_account_id or "").strip()
    if not ident:
        raise CuentaNoActiveError()
    return {"bank_account_id": ident}


def _qr_general_de_comercio(comercio: Comercio) -> Cobro | None:
    return Cobro.objects.filter(
        comercio=comercio,
        canal=Movimiento.Canal.QR_GENERAL,
    ).first()
