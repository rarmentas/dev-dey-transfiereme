"""Excepciones de dominio de movimientos (sin red y sin DRF)."""


class TransicionInvalida(Exception):
    """El estado pedido no está permitido para el movimiento."""
