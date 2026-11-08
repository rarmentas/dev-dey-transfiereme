"""Helpers de ámbito para cobros y consultas (sin HTTP)."""

from typing import Any

from django.db.models import Model, QuerySet
from django.http import HttpRequest, QueryDict

from ambito.exceptions import ComercioEnCuerpoError, SinAmbitoError
from ambito.models import Comercio

# Claves prohibidas en el cuerpo y en la query (C5); case-sensitive.
_CLAVES_COMERCIO_EN_CUERPO = frozenset({"comercio", "comercio_id"})


def rechazar_comercio_en_cuerpo(datos: dict[str, Any]) -> None:
    """
    Rechaza si el cliente envía el comercio en el cuerpo.

    Claves prohibidas: ``comercio``, ``comercio_id`` (case-sensitive).
    """
    for clave in datos:
        if clave in _CLAVES_COMERCIO_EN_CUERPO:
            raise ComercioEnCuerpoError(clave)


def rechazar_comercio_en_query(parametros: QueryDict) -> None:
    """
    Rechaza si el cliente envía el comercio en la cadena de consulta.

    Claves prohibidas: ``comercio``, ``comercio_id`` (case-sensitive).
    """
    for clave in parametros:
        if clave in _CLAVES_COMERCIO_EN_CUERPO:
            raise ComercioEnCuerpoError(clave)


def requerir_comercio(request: HttpRequest) -> Comercio:
    """Devuelve el comercio de la petición o lanza SinAmbitoError."""
    comercio = getattr(request, "comercio", None)
    if comercio is None:
        raise SinAmbitoError()
    return comercio


def preparar_operacion_cobro(request: HttpRequest, datos: dict[str, Any]) -> Comercio:
    """Valida cuerpo y devuelve el comercio de la sesión para una operación de cobro."""
    rechazar_comercio_en_cuerpo(datos)
    return requerir_comercio(request)


def filtrar_por_comercio(queryset: QuerySet[Model], comercio: Comercio) -> QuerySet[Model]:
    """Filtra un queryset por el campo ``comercio`` del modelo."""
    return queryset.filter(comercio=comercio)


def obtener_por_id_en_ambito(
    queryset: QuerySet[Model],
    comercio: Comercio,
    pk: Any,
) -> Model | None:
    """Devuelve la instancia si pertenece al comercio; si no, None (vista → 404)."""
    return filtrar_por_comercio(queryset, comercio).filter(pk=pk).first()
