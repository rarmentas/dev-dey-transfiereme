"""Excepciones de dominio de movimientos (sin red y sin DRF)."""


class TransicionInvalida(Exception):
    """El estado pedido no está permitido para el movimiento."""


class AvisoSinCobro(Exception):
    """El aviso no corresponde a un cobro persistido."""


class AvisoInvalido(Exception):
    """El aviso no tiene un tipo que Cody sepa aplicar."""
