"""Alta de una venta por QR. No habla con la red: usa el puerto inyectado."""

import logging
import re
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal, DecimalException, InvalidOperation, localcontext

from django.db import transaction
from django.utils import timezone

from ambito.models import Comercio
from movimientos.models import Cobro, Movimiento
from pey.desarrollo import AdaptadorDesarrollo
from pey.puerto import PuertoPey
from pey.seleccion import obtener_puerto

logger = logging.getLogger(__name__)

VENTA_EXPIRACION_S = 600

_NUM_REF = re.compile(r"^[0-9]{1,7}$")
_CERO = Decimal("0")
_CENTAVO = Decimal("0.01")
# Exclusivo. El QR de pey no admite 10**10 ni más.
_TOPE_MONTO = Decimal("10000000000")
_PREC_MONTO = 50
_CONCEPTO_VACIO = "Transferencia"
# Mismo tope que Movimiento.concepto y Cobro.concepto (max_length=500).
_LARGO_CONCEPTO = 500
_REF_VACIA = "0"


class ValidacionVenta(Exception):
    """El alta no cumple el contrato. No se llamó al puerto."""

    def __init__(self, campo: str, mensaje: str) -> None:
        self.campo = campo
        super().__init__(mensaje)


class ReferenciaInvalida(ValidacionVenta):
    """La referencia trae algo que no es vacío ni 1–7 dígitos."""

    def __init__(self) -> None:
        super().__init__(
            "referencia",
            "La referencia debe ser numérica, de 1 a 7 dígitos.",
        )


class MontoInvalido(ValidacionVenta):
    def __init__(self, mensaje: str) -> None:
        super().__init__("monto", mensaje)


class ConceptoInvalido(ValidacionVenta):
    def __init__(self, mensaje: str) -> None:
        super().__init__("concepto", mensaje)


class CuentaNoActive(Exception):
    """El puerto dice que la cuenta no está ACTIVE. No se crea el QR."""


@dataclass(frozen=True)
class VentaCreada:
    movimiento: Movimiento
    cobro: Cobro
    qr_string: str


def crear_venta_qr(
    *,
    comercio: Comercio,
    monto: Decimal,
    concepto: str,
    referencia: str,
    puerto: PuertoPey | None = None,
) -> VentaCreada:
    """Valida, pide el QR y solo entonces persiste cobro y movimiento."""
    referencia_ok = _referencia(referencia)
    monto_ok = _monto(monto)
    concepto_ok = _concepto(concepto)

    if puerto is None:
        puerto = obtener_puerto()

    if not puerto.cuenta_active(comercio):
        raise CuentaNoActive()

    # Fuera de la transacción: si el puerto falla, no queda nada escrito.
    qr = puerto.crear_qr(
        monto=monto_ok,
        concepto=concepto_ok,
        expiracion_s=VENTA_EXPIRACION_S,
        num_ref=referencia_ok,
    )

    origen = (
        Movimiento.Origen.ORIGEN_DESARROLLO
        if isinstance(puerto, AdaptadorDesarrollo)
        else Movimiento.Origen.ORIGEN_PEY
    )
    vence_en = timezone.now() + timedelta(seconds=VENTA_EXPIRACION_S)
    # Si la base falla, el QR ya existe en pey pero qr_string no se entrega:
    # nadie puede pagar ese QR. La reconciliación queda pendiente (historia 3.2).
    try:
        with transaction.atomic():
            cobro = Cobro.objects.create(
                comercio=comercio,
                canal=Movimiento.Canal.QR_VENTA,
                monto=monto_ok,
                concepto=concepto_ok,
                vence_en=vence_en,
                pey_qr_id=qr.id,
                qr_string=qr.qr_string,
            )
            movimiento = Movimiento.objects.create(
                comercio=comercio,
                cobro=cobro,
                canal=Movimiento.Canal.QR_VENTA,
                monto=monto_ok,
                concepto=concepto_ok,
                estado=Movimiento.Estado.PENDIENTE,
                origen=origen,
            )
    except Exception:
        logger.error(
            "qr de venta creado en pey sin persistir pey_qr_id=%s comercio_id=%s",
            qr.id,
            comercio.pk,
        )
        raise
    return VentaCreada(movimiento=movimiento, cobro=cobro, qr_string=qr.qr_string)


def _referencia(referencia: str | None) -> str:
    if referencia is None or referencia == "":
        return _REF_VACIA
    if not isinstance(referencia, str) or _NUM_REF.fullmatch(referencia) is None:
        raise ReferenciaInvalida()
    return referencia


def _monto(monto: Decimal) -> Decimal:
    if not isinstance(monto, Decimal):
        raise MontoInvalido("El monto debe ser un número decimal.")
    try:
        with localcontext() as ctx:
            ctx.prec = _PREC_MONTO
            ctx.traps[InvalidOperation] = True
            if not monto.is_finite():
                raise MontoInvalido("El monto debe ser un número finito.")
            if monto <= _CERO:
                raise MontoInvalido("El monto debe ser mayor que 0.")
            exponente = monto.as_tuple().exponent
            if not isinstance(exponente, int) or exponente < -2:
                raise MontoInvalido("El monto no admite más de 2 decimales.")
            if monto >= _TOPE_MONTO:
                raise MontoInvalido("El monto no cabe en el QR.")
            return monto.quantize(_CENTAVO)
    except DecimalException as exc:
        raise MontoInvalido("El monto no se puede representar.") from exc


def _concepto(concepto: str | None) -> str:
    if concepto is None:
        return _CONCEPTO_VACIO
    if not isinstance(concepto, str):
        raise ConceptoInvalido("El concepto debe ser texto.")
    if concepto.strip() == "":
        return _CONCEPTO_VACIO
    if len(concepto) > _LARGO_CONCEPTO:
        raise ConceptoInvalido("El concepto no puede pasar de 500 caracteres.")
    return concepto
