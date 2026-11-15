"""Validación de la configuración del modo de pedidos."""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def demo_activo() -> bool:
    valor = settings.DEMO_MODE.strip().lower()
    if valor not in ("", "true", "false"):
        raise ImproperlyConfigured("DEMO_MODE debe ser true o false")
    return valor == "true"


def politica_cobro_version() -> str:
    return settings.POLITICA_COBRO_VERSION or (
        "demo-1" if demo_activo() else "normal-1"
    )


def cobro_habilitado() -> bool:
    return settings.PEDIDOS_COBRO_HABILITADO


def validar_configuracion() -> None:
    demo = demo_activo()
    if cobro_habilitado():
        raise ImproperlyConfigured("el cobro de pedidos no existe en este release")
    adaptador = settings.NUCLEO_ADAPTADOR.strip().lower()
    if not settings.DEBUG:
        if not settings.DEMO_MODE.strip():
            raise ImproperlyConfigured("DEMO_MODE debe declararse explícitamente")
        if adaptador not in ("", "real"):
            raise ImproperlyConfigured("NUCLEO_ADAPTADOR debe ser real")
        if not settings.POLITICA_COBRO_VERSION.strip():
            raise ImproperlyConfigured("POLITICA_COBRO_VERSION es requerida")
    if demo:
        from pey.seleccion import modo_adaptador

        if (
            settings.DEBUG
            or adaptador not in ("", "real")
            or modo_adaptador() != "produccion"
            or not settings.DEMO_PEY_BANK_ACCOUNT_ID.strip()
        ):
            raise ImproperlyConfigured("Configuración de demostración inválida")


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
