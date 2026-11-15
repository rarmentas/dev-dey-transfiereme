"""Fábrica del puerto y del lector de procedencia."""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

from config.modo import validar_stub_sin_credenciales


def obtener_lector():
    return import_string(settings.PEDIDOS_LECTOR_PROCEDENCIA)()


def obtener_nucleo():
    adaptador = settings.NUCLEO_ADAPTADOR.strip().lower()
    if adaptador in ("", "real"):
        from pedidos.nucleo_real import NucleoRealV1

        return NucleoRealV1(obtener_lector())
    if adaptador == "stub" and settings.NUCLEO_STUB_PERMITIDO:
        validar_stub_sin_credenciales()
        from pedidos.stub import NucleoStubV1

        return NucleoStubV1(obtener_lector())
    raise ImproperlyConfigured("Adaptador del núcleo no permitido.")
