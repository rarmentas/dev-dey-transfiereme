"""Reglas de QR y notificación. Las aplican los dos adaptadores antes de actuar."""

import re
from dataclasses import dataclass
from decimal import Decimal, DecimalException, InvalidOperation, localcontext

from pey.tipos import ParametroInvalido

_NUM_REF = re.compile(r"^[0-9]{1,7}$")
_TELEFONO = re.compile(r"^[0-9]{10}$")
_CERO = Decimal("0")
_CENTAVO = Decimal("0.01")
_TOPE_PN = Decimal("1000000")
# Exclusivo. Decimal(12, 2) llega hasta 9999999999.99.
_TOPE_QR = Decimal("10000000000")
_PREC_MONTO = 50
_CONCEPTO_VACIO = "Transferencia"


@dataclass(frozen=True)
class QrValidado:
    monto: Decimal
    concepto: str
    expiracion_s: int
    num_ref: str


@dataclass(frozen=True)
class NotificacionValidada:
    monto: Decimal
    telefono: str
    concepto: str
    expiracion_s: int
    num_ref: str


def validar_qr(
    *,
    monto: Decimal,
    concepto: str,
    expiracion_s: int,
    num_ref: str,
) -> QrValidado:
    return QrValidado(
        monto=_monto(monto, tope=_TOPE_QR, exclusivo_tope=True, permitir_cero=True),
        concepto=_concepto(concepto),
        expiracion_s=_expiracion_qr(expiracion_s),
        num_ref=_num_ref(num_ref),
    )


def validar_monto_pago(monto: Decimal) -> Decimal:
    """Monto positivo de un aviso simulado o real (hasta 2 decimales)."""
    return _monto(monto, tope=_TOPE_PN, exclusivo_tope=False, permitir_cero=False)


def validar_notificacion(
    *,
    monto: Decimal,
    telefono: str,
    concepto: str,
    expiracion_s: int,
    num_ref: str,
) -> NotificacionValidada:
    return NotificacionValidada(
        monto=_monto(monto, tope=_TOPE_PN, exclusivo_tope=False, permitir_cero=False),
        telefono=_telefono(telefono),
        concepto=_concepto(concepto),
        expiracion_s=_expiracion_pn(expiracion_s),
        num_ref=_num_ref(num_ref),
    )


def _monto(
    monto: Decimal,
    *,
    tope: Decimal,
    exclusivo_tope: bool,
    permitir_cero: bool,
) -> Decimal:
    if not isinstance(monto, Decimal):
        raise ParametroInvalido("monto debe ser un Decimal")
    try:
        with localcontext() as ctx:
            ctx.prec = _PREC_MONTO
            ctx.traps[InvalidOperation] = True
            if not monto.is_finite():
                raise ParametroInvalido("monto debe ser finito")
            if monto.is_signed():
                raise ParametroInvalido("monto no puede ser negativo")
            exponente = monto.as_tuple().exponent
            if not isinstance(exponente, int) or exponente < -2:
                raise ParametroInvalido("monto no admite más de 2 decimales")
            if not permitir_cero and monto <= _CERO:
                raise ParametroInvalido("monto debe ser mayor que 0")
            if exclusivo_tope:
                if monto >= tope:
                    raise ParametroInvalido("monto no cabe en el QR")
            elif monto > tope:
                raise ParametroInvalido("monto no puede pasar de 1000000")
            return monto.quantize(_CENTAVO)
    except DecimalException as exc:
        raise ParametroInvalido("monto no se puede representar") from exc


def _entero(valor: int, nombre: str) -> int:
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise ParametroInvalido(f"{nombre} debe ser un entero")
    return valor


def _expiracion_qr(expiracion_s: int) -> int:
    valor = _entero(expiracion_s, "expiracion_s")
    if valor < 0 or (valor != 0 and valor < 360):
        raise ParametroInvalido("expiracion_s debe ser 0 o al menos 360")
    return valor


def _expiracion_pn(expiracion_s: int) -> int:
    valor = _entero(expiracion_s, "expiracion_s")
    if valor < 360:
        raise ParametroInvalido("expiracion_s debe ser al menos 360")
    return valor


def _num_ref(num_ref: str) -> str:
    if not isinstance(num_ref, str) or _NUM_REF.fullmatch(num_ref) is None:
        raise ParametroInvalido("num_ref debe ser de 1 a 7 dígitos")
    return num_ref


def _telefono(telefono: str) -> str:
    if not isinstance(telefono, str) or _TELEFONO.fullmatch(telefono) is None:
        raise ParametroInvalido("telefono debe ser de 10 dígitos")
    return telefono


def _concepto(concepto: str) -> str:
    if not isinstance(concepto, str):
        raise ParametroInvalido("concepto debe ser texto")
    if concepto.strip() == "":
        return _CONCEPTO_VACIO
    return concepto
