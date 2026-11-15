"""Reloj e infraestructura determinista para fixtures."""

from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

from .v1 import (
    ContextoCanalV1,
    ContextoConsumidorV1,
    MensajeProcedenciaDTO,
    ResumenEnviadoDTO,
)


def id_determinista(escenario: str, clave: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"{escenario}:{clave}"))


class RelojFijo:
    def __init__(self, instante: datetime | None = None):
        self.instante = instante or datetime(2026, 1, 1, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.instante


class LectorFixtureV1:
    def __init__(self):
        self.comercios: dict[tuple[str, str], str] = {}
        self.mensajes: dict[tuple[ContextoCanalV1, str], MensajeProcedenciaDTO] = {}
        self.resumenes: dict[tuple[ContextoCanalV1, str], ResumenEnviadoDTO] = {}

    def resolver_comercio(
        self, ctx: ContextoCanalV1 | ContextoConsumidorV1
    ) -> str | None:
        return self.comercios.get((ctx.instancia_id, ctx.sesion_id))

    def leer_mensaje(
        self, ctx: ContextoCanalV1, mensaje_id: str
    ) -> MensajeProcedenciaDTO | None:
        return self.mensajes.get((ctx, mensaje_id))

    def leer_resumen(
        self, ctx: ContextoCanalV1, cotizacion_id: str
    ) -> ResumenEnviadoDTO | None:
        return self.resumenes.get((ctx, cotizacion_id))
