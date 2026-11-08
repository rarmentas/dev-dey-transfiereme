"""Excepciones de dominio del ámbito de comercio (sin acoplar a DRF)."""


class AmbitoError(Exception):
    """Base para errores de ámbito."""


class SinAmbitoError(AmbitoError):
    """El usuario autenticado no tiene comercio asociado por membresía."""

    def __init__(self) -> None:
        super().__init__(
            "Su sesión no tiene un comercio asignado. "
            "Solicite al administrador que configure su membresía."
        )


class ComercioEnCuerpoError(AmbitoError):
    """La petición intentó enviar el comercio en el cuerpo (prohibido por C5)."""

    def __init__(self, clave: str) -> None:
        super().__init__(
            f"No debe enviar el campo «{clave}» en la petición; "
            "el servidor determina su comercio por membresía."
        )
