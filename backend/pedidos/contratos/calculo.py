"""Cálculo de importes en centavos."""

from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable

from .v1 import TOTAL_MAXIMO_CENTAVOS, CodigoError
from .validacion import ErrorContrato, validar_cantidad


def subtotal_centavos(cantidad: Decimal, precio_centavos: int) -> int:
    cantidad = validar_cantidad(cantidad)
    if type(precio_centavos) is not int or precio_centavos <= 0:
        raise ErrorContrato(CodigoError.PAYLOAD_INVALIDO, "Precio inválido.")
    subtotal = int(
        (cantidad * precio_centavos).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )
    if subtotal <= 0:
        raise ErrorContrato(CodigoError.PAYLOAD_INVALIDO, "Subtotal inválido.")
    return subtotal


def total_centavos(subtotales: Iterable[int]) -> int:
    valores = list(subtotales)
    if not valores or any(type(valor) is not int or valor <= 0 for valor in valores):
        raise ErrorContrato(CodigoError.PAYLOAD_INVALIDO, "Subtotales inválidos.")
    total = sum(valores)
    if total > TOTAL_MAXIMO_CENTAVOS:
        raise ErrorContrato(CodigoError.PAYLOAD_INVALIDO, "Total sobre el límite.")
    return total


def importe_efectivo(total: int, demo_mode: bool) -> int:
    total_centavos([total])
    return 1 if demo_mode else total
