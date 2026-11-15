"""Validación de la configuración del modo de pedidos."""

import logging
import os
import re
from typing import NamedTuple

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


POLITICA_NORMAL = "normal-1"
POLITICA_DEMO = "demo-1"
logger = logging.getLogger(__name__)


class ModoCobro(NamedTuple):
    demo: bool
    politica: str


def politica_de(demo: bool) -> str:
    return POLITICA_DEMO if demo else POLITICA_NORMAL


def modo_de_comercio(comercio) -> ModoCobro:
    from ambito.models import Comercio

    pk = getattr(comercio, "pk", comercio)
    demo = Comercio.objects.values_list("es_demo", flat=True).get(pk=pk)
    return ModoCobro(demo, politica_de(demo))


def destino_demo() -> str | None:
    valor = settings.DEMO_PEY_BANK_ACCOUNT_ID.strip()
    return valor if re.fullmatch(r"[0-9A-HJKMNP-TV-Z]{26}", valor) else None


def cobro_habilitado() -> bool:
    return settings.PEDIDOS_COBRO_HABILITADO


def validar_stub_sin_credenciales() -> None:
    """Impide simular con credenciales financieras presentes."""
    if settings.PEY_API_KEY or settings.PEY_ADAPTADOR.strip().lower() == "produccion":
        raise ImproperlyConfigured("El stub no admite credenciales financieras")


def validar_configuracion() -> None:
    adaptador = settings.NUCLEO_ADAPTADOR.strip().lower()
    if adaptador == "stub":
        validar_stub_sin_credenciales()
    if not settings.DEBUG:
        if adaptador not in ("", "real"):
            raise ImproperlyConfigured("NUCLEO_ADAPTADOR debe ser real")
    from pey.seleccion import modo_adaptador

    rol = settings.CODY_ROL.strip().lower()
    if rol in ("canal", "stt") and settings.PEY_API_KEY:
        raise ImproperlyConfigured("El rol no admite la llave pey")
    if cobro_habilitado():
        if (
            adaptador not in ("", "real")
            or settings.DEBUG
            or modo_adaptador() != "produccion"
        ):
            raise ImproperlyConfigured("Configuración de cobro inválida")
        if rol in ("web", "cobros") and not settings.PEY_API_KEY:
            raise ImproperlyConfigured("PEY_API_KEY es requerida para este rol")
    for clave in ("DEMO_MODE", "POLITICA_COBRO_VERSION"):
        if clave in os.environ:
            logger.warning(
                "%s ignorada; el demo es por comercio (designar_comercio_demo)", clave
            )
    if settings.DEMO_PEY_BANK_ACCOUNT_ID.strip() and not destino_demo():
        logger.warning("DEMO_PEY_BANK_ACCOUNT_ID no es un ULID válido")


def respuesta_bloqueada_en_demo():
    """Bloquea las rutas de emisión legacy durante la demostración."""
    from rest_framework.response import Response

    return Response(
        {
            "codigo": "RUTA_BLOQUEADA_EN_DEMO",
            "detail": "Esta acción no está disponible en modo demostración.",
        },
        status=403,
    )
