"""Autenticación del cuerpo original de WAHA."""

import hashlib
import hmac

from django.conf import settings


class FirmaInvalida(Exception):
    pass


def verificar_firma(cuerpo: bytes, headers) -> None:
    secreto = settings.WAHA_WEBHOOK_SECRET
    firma = headers.get("X-Webhook-Hmac", "")
    algoritmo = headers.get("X-Webhook-Hmac-Algorithm", "")
    if not secreto or algoritmo.lower() != "sha512":
        raise FirmaInvalida
    esperado = hmac.new(secreto.encode(), cuerpo, hashlib.sha512).hexdigest()
    if not firma.isascii() or not hmac.compare_digest(esperado, firma):
        raise FirmaInvalida
