"""Tipos del puerto pey. Los comparten el adaptador de desarrollo y el de producción."""

from dataclasses import dataclass


@dataclass(frozen=True)
class QrCreado:
    id: str
    qr_string: str


@dataclass(frozen=True)
class NotificacionCreada:
    transaction_id: str
    codi_id: str


class ErrorPey(Exception):
    """Fallo de configuración, de transporte o devuelto por pey.

    ``puede_haberse_creado`` es True cuando la petición pudo llegar a pey
    y no sabemos si el cobro quedó creado (timeout, 5xx, estado inesperado
    o un 2xx con cuerpo ilegible). El llamador no debe reintentar a ciegas
    en ese caso: un segundo intento puede cobrar dos veces.
    """

    def __init__(
        self,
        tipo: str,
        mensaje: str,
        request_id: str | None = None,
        puede_haberse_creado: bool = False,
    ) -> None:
        self.tipo = tipo
        self.mensaje = mensaje
        self.request_id = request_id
        self.puede_haberse_creado = puede_haberse_creado
        super().__init__(mensaje)


class ParametroInvalido(ValueError):
    """El llamado no cumple el contrato. No se hizo ninguna petición."""
