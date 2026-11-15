"""Alta de una venta por QR. No habla con la red: usa el puerto inyectado."""

import re
from dataclasses import dataclass
from decimal import Decimal, DecimalException, InvalidOperation, localcontext

from ambito.models import Comercio
from movimientos.models import Cobro, Movimiento
from pey.puerto import PuertoPey

VENTA_EXPIRACION_S = 600

_NUM_REF = re.compile(r"^[0-9]{1,7}$")
_TELEFONO = re.compile(r"^[0-9]{10}$")
_CERO = Decimal("0")
_CENTAVO = Decimal("0.01")
# Exclusivo. El QR de pey no admite 10**10 ni más.
_TOPE_MONTO = Decimal("10000000000")
# Inclusivo. La notificación de pey no pasa de 1 000 000.
_TOPE_NOTIFICACION = Decimal("1000000")
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


class TelefonoInvalido(ValidacionVenta):
    """El teléfono no es de 10 dígitos. No se llamó al puerto."""

    def __init__(self) -> None:
        super().__init__("telefono", "El teléfono debe ser de 10 dígitos.")


class CuentaNoActive(Exception):
    """El puerto dice que la cuenta no está ACTIVE. No se crea el QR."""


@dataclass(frozen=True)
class VentaCreada:
    movimiento: Movimiento
    cobro: Cobro
    qr_string: str
    transaction_id: str = ""


def crear_venta_qr(
    *, comercio: Comercio, monto: Decimal, concepto: str, referencia: str,
    clave: str, puerto: PuertoPey | None = None,
) -> VentaCreada:
    from pedidos.servicios.legado import emitir_legado

    return emitir_legado(
        comercio, "qr_venta", _monto(monto), _concepto(concepto),
        _referencia(referencia), "", clave, puerto,
    )


def crear_venta_notificacion(
    *, comercio: Comercio, monto: Decimal, telefono: str, concepto: str,
    referencia: str, clave: str, puerto: PuertoPey | None = None,
) -> VentaCreada:
    from pedidos.servicios.legado import emitir_legado

    return emitir_legado(
        comercio, "notificacion", _monto(monto, tope=_TOPE_NOTIFICACION,
                                         exclusivo=False), _concepto(concepto),
        _referencia(referencia), _telefono(telefono), clave, puerto,
    )


def _referencia(referencia: str | None) -> str:
    if referencia is None or referencia == "":
        return _REF_VACIA
    if not isinstance(referencia, str) or _NUM_REF.fullmatch(referencia) is None:
        raise ReferenciaInvalida()
    return referencia


def _monto(
    monto: Decimal,
    *,
    tope: Decimal = _TOPE_MONTO,
    exclusivo: bool = True,
) -> Decimal:
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
            if exclusivo:
                if monto >= tope:
                    raise MontoInvalido("El monto no cabe en el QR.")
            elif monto > tope:
                raise MontoInvalido("El monto no puede pasar de 1000000.")
            return monto.quantize(_CENTAVO)
    except DecimalException as exc:
        raise MontoInvalido("El monto no se puede representar.") from exc


def _telefono(telefono: str) -> str:
    if not isinstance(telefono, str) or _TELEFONO.fullmatch(telefono) is None:
        raise TelefonoInvalido()
    return telefono


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
