"""Agrupación del tablero por día local, canal y concepto visible.

No suma ``origen_pey`` con ``origen_desarrollo``. El día sale de
``pagado_en`` en America/Mexico_City, no de la zona del servidor.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from movimientos.models import Movimiento

ZONA_NOMBRE = "America/Mexico_City"
ZONA = ZoneInfo(ZONA_NOMBRE)
CONCEPTO_VACIO = "transferencia"

_DIA = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class Fila:
    dia: date
    canal: str
    concepto: str
    etiqueta: str
    total: Decimal
    cantidad: int


@dataclass
class _Grupo:
    dia: date
    canal: str
    concepto: str
    etiqueta: str
    pagado_en: datetime
    pk: int
    total: Decimal
    cantidad: int


def normalizar_concepto(texto: str | None) -> str:
    """Minúsculas y un solo espacio entre palabras. Vacío → ``transferencia``."""
    colapsado = " ".join((texto or "").split())
    if not colapsado:
        return CONCEPTO_VACIO
    return colapsado.lower()


def interpretar_dia(texto: str) -> date:
    """Día ``YYYY-MM-DD``. Otro formato lanza ``ValueError``."""
    if not isinstance(texto, str) or _DIA.fullmatch(texto) is None:
        raise ValueError("Fecha inválida. Use YYYY-MM-DD.")
    try:
        return date.fromisoformat(texto)
    except ValueError:
        raise ValueError("Fecha inválida. Use YYYY-MM-DD.") from None


def dia_local(momento: datetime) -> date:
    """Fecha civil de ``momento`` en America/Mexico_City."""
    if momento.tzinfo is None:
        raise ValueError("pagado_en tiene que traer zona horaria.")
    return momento.astimezone(ZONA).date()


def inicio_dia_local(dia: date) -> datetime:
    """00:00 de ``dia`` en America/Mexico_City, con zona."""
    return datetime(dia.year, dia.month, dia.day, tzinfo=ZONA)


def partir_por_origen(
    movimientos: Iterable[Movimiento],
) -> tuple[list[Movimiento], list[Movimiento]]:
    """Separa confirmado (``origen_pey``) y desarrollo. No los mezcla."""
    confirmado: list[Movimiento] = []
    desarrollo: list[Movimiento] = []
    for movimiento in movimientos:
        if movimiento.origen == Movimiento.Origen.ORIGEN_PEY:
            confirmado.append(movimiento)
        elif movimiento.origen == Movimiento.Origen.ORIGEN_DESARROLLO:
            desarrollo.append(movimiento)
    return confirmado, desarrollo


def agrupar(movimientos: Iterable[Movimiento]) -> list[Fila]:
    """Solo ``pagado``. Llave ``(día local, canal, concepto visible normalizado)``."""
    grupos: dict[tuple[date, str, str], _Grupo] = {}
    for movimiento in movimientos:
        if movimiento.estado != Movimiento.Estado.PAGADO or movimiento.pagado_en is None:
            continue
        dia = dia_local(movimiento.pagado_en)
        concepto = normalizar_concepto(movimiento.concepto_visible)
        llave = (dia, movimiento.canal, concepto)
        grupo = grupos.get(llave)
        pk = movimiento.pk or 0
        if grupo is None:
            grupos[llave] = _Grupo(
                dia=dia,
                canal=movimiento.canal,
                concepto=concepto,
                etiqueta=movimiento.concepto_visible,
                pagado_en=movimiento.pagado_en,
                pk=pk,
                total=movimiento.monto,
                cantidad=1,
            )
            continue
        grupo.total += movimiento.monto
        grupo.cantidad += 1
        if (movimiento.pagado_en, pk) >= (grupo.pagado_en, grupo.pk):
            grupo.pagado_en = movimiento.pagado_en
            grupo.pk = pk
            grupo.etiqueta = movimiento.concepto_visible

    filas = [
        Fila(
            dia=grupo.dia,
            canal=grupo.canal,
            concepto=grupo.concepto,
            etiqueta=grupo.etiqueta,
            total=grupo.total,
            cantidad=grupo.cantidad,
        )
        for grupo in grupos.values()
    ]
    filas.sort(key=lambda fila: (-fila.dia.toordinal(), fila.canal, fila.concepto))
    return filas
