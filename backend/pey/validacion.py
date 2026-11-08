"""Reglas de QR y notificación. Las aplican los dos adaptadores antes de actuar."""

import re
from dataclasses import dataclass
from decimal import Decimal

from pey.tipos import ParametroInvalido

_NUM_REF = re.compile(r"^[0-9]{1,7}$")
_TELEFONO = re.compile(r"^[0-9]{10}$")
_CERO = Decimal("0")
_TOPE_PN = Decimal("1000000")
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
        monto=_monto(monto, minimo=_CERO),
        concepto=_concepto(concepto),
        expiracion_s=_expiracion_qr(expiracion_s),
        num_ref=_num_ref(num_ref),
    )


def validar_notificacion(
    *,
    monto: Decimal,
    telefono: str,
    concepto: str,
    expiracion_s: int,
    num_ref: str,
) -> NotificacionValidada:
    return NotificacionValidada(
        monto=_monto(monto, minimo=_CERO, exclusivo=True, tope=_TOPE_PN),
        telefono=_telefono(telefono),
        concepto=_concepto(concepto),
        expiracion_s=_expiracion_pn(expiracion_s),
        num_ref=_num_ref(num_ref),
    )


def _monto(
    monto: Decimal,
    *,
    minimo: Decimal,
    exclusivo: bool = False,
    tope: Decimal | None = None,
) -> Decimal:
    if not isinstance(monto, Decimal) or not monto.is_finite():
        raise ParametroInvalido("monto debe ser un Decimal finito")
    # normalize quita ceros de cola: 10.500 es 10.50; 0.005 sigue teniendo 3 decimales.
    exponente = monto.normalize().as_tuple().exponent
    if isinstance(exponente, str) or exponente < -2:
        raise ParametroInvalido("monto no admite más de 2 decimales")
    if exclusivo:
        if monto <= minimo:
            raise ParametroInvalido("monto debe ser mayor que 0")
    elif monto < minimo:
        raise ParametroInvalido("monto no puede ser negativo")
    if tope is not None and monto > tope:
        raise ParametroInvalido("monto no puede pasar de 1000000")
    return monto


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
    if concepto == "":
        return _CONCEPTO_VACIO
    return concepto
