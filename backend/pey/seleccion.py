"""Elige el adaptador. El de desarrollo no corre con DEBUG apagado."""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from pey.desarrollo import AdaptadorDesarrollo
from pey.produccion import AdaptadorProduccion
from pey.puerto import PuertoPey


def obtener_puerto() -> PuertoPey:
    elegido = (getattr(settings, "PEY_ADAPTADOR", "") or "").strip()
    if not elegido:
        elegido = "desarrollo" if settings.DEBUG else "produccion"
    if elegido == "desarrollo":
        if not settings.DEBUG:
            raise ImproperlyConfigured(
                "PEY_ADAPTADOR=desarrollo solo se permite con DEBUG."
            )
        return AdaptadorDesarrollo()
    if elegido == "produccion":
        return AdaptadorProduccion()
    raise ImproperlyConfigured(
        "PEY_ADAPTADOR debe ser 'desarrollo' o 'produccion'."
    )
