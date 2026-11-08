"""Elige el adaptador. El de desarrollo no corre con DEBUG apagado ni con llave."""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from pey.desarrollo import AdaptadorDesarrollo
from pey.produccion import AdaptadorProduccion
from pey.puerto import PuertoPey


def modo_adaptador() -> str:
    """Devuelve ``desarrollo`` o ``produccion``. El primero solo en local."""
    elegido = (getattr(settings, "PEY_ADAPTADOR", "") or "").strip().lower()
    if not elegido:
        elegido = "desarrollo" if settings.DEBUG else "produccion"
    if elegido == "desarrollo":
        if not settings.DEBUG:
            raise ImproperlyConfigured(
                "PEY_ADAPTADOR=desarrollo solo se permite con DEBUG."
            )
        if settings.PEY_API_KEY:
            raise ImproperlyConfigured(
                "PEY_ADAPTADOR=desarrollo no admite PEY_API_KEY."
            )
        return "desarrollo"
    if elegido == "produccion":
        return "produccion"
    raise ImproperlyConfigured(
        "PEY_ADAPTADOR debe ser 'desarrollo' o 'produccion'."
    )


def obtener_puerto() -> PuertoPey:
    if modo_adaptador() == "desarrollo":
        return AdaptadorDesarrollo()
    return AdaptadorProduccion()
