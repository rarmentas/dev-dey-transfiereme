"""Alta del QR general de un comercio vía el puerto pey (sin HTTP aquí)."""

from dataclasses import dataclass
from decimal import Decimal

from django.db import IntegrityError, transaction

from ambito.cuenta import cuenta_apta, cuenta_por_defecto
from ambito.exceptions import CuentaNoActiveError
from ambito.models import Comercio
from movimientos.cobro_qr import preparar_alta_qr_general
from config.modo import modo_de_comercio
from ambito.candados import bloquear_comercio
from movimientos.exceptions import DemoBloqueado, QrGeneralNoDisponible
from movimientos.models import Cobro, Movimiento
from pey.produccion import AdaptadorProduccion
from pey.seleccion import obtener_puerto
from pey.tipos import QrCreado

_CONCEPTO_QR_GENERAL = "Transferencia"


@dataclass(frozen=True)
class ResultadoAltaQrGeneral:
    cobro: Cobro
    creado: bool


def alta_qr_general(comercio: Comercio) -> ResultadoAltaQrGeneral:
    if modo_de_comercio(comercio).demo:
        raise DemoBloqueado()
    preparar_alta_qr_general(comercio)
    if comercio.cuentas.count() > 1:
        raise QrGeneralNoDisponible()
    puerto = obtener_puerto()
    # En producción se exige la cuenta antes de reutilizar un QR viejo.
    cuenta = _cuenta_de_produccion(puerto, comercio)
    ident = cuenta.get("bank_account_id", "")

    existente = _qr_general_de_comercio(comercio)
    if existente is not None:
        if existente.pey_bank_account_id != ident:
            raise QrGeneralNoDisponible()
        return ResultadoAltaQrGeneral(cobro=existente, creado=False)

    qr = _pedir_qr(puerto, cuenta)
    try:
        with transaction.atomic():
            comercio = bloquear_comercio(comercio)
            if modo_de_comercio(comercio).demo:
                raise DemoBloqueado()
            cobro = Cobro.objects.create(
                comercio=comercio,
                canal=Movimiento.Canal.QR_GENERAL,
                monto=Decimal("0"),
                concepto=_CONCEPTO_QR_GENERAL,
                vence_en=None,
                pey_qr_id=qr.id,
                qr_string=qr.qr_string,
                pey_bank_account_id=ident,
                cuenta=cuenta_por_defecto(comercio),
            )
            return ResultadoAltaQrGeneral(cobro=cobro, creado=True)
    except IntegrityError:
        existente = _qr_general_de_comercio(comercio)
        if existente is None:
            raise
        if existente.pey_bank_account_id != ident:
            raise QrGeneralNoDisponible() from None
        return ResultadoAltaQrGeneral(cobro=existente, creado=False)


def _cuenta_de_produccion(puerto: object, comercio: Comercio) -> dict[str, str]:
    if not isinstance(puerto, AdaptadorProduccion):
        return {}
    cuenta = cuenta_por_defecto(comercio)
    ident = cuenta.pey_bank_account_id if cuenta else ""
    if not cuenta_apta(cuenta):
        raise CuentaNoActiveError()
    return {"bank_account_id": ident}


def _pedir_qr(puerto: object, cuenta: dict[str, str]) -> QrCreado:
    return puerto.crear_qr(
        monto=Decimal("0"),
        concepto="",
        expiracion_s=0,
        num_ref="0",
        **cuenta,
    )


def _qr_general_de_comercio(comercio: Comercio) -> Cobro | None:
    return Cobro.objects.filter(
        comercio=comercio,
        canal=Movimiento.Canal.QR_GENERAL,
    ).first()
