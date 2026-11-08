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
    """Fallo de configuración, de transporte o devuelto por pey."""

    def __init__(
        self,
        tipo: str,
        mensaje: str,
        request_id: str | None = None,
    ) -> None:
        self.tipo = tipo
        self.mensaje = mensaje
        self.request_id = request_id
        super().__init__(mensaje)


class ParametroInvalido(ValueError):
    """El llamado no cumple el contrato. No se hizo ninguna petición."""
