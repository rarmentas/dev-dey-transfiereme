"""Verifica la firma Standard Webhooks sobre el cuerpo crudo."""

from django.conf import settings
from standardwebhooks import Webhook, WebhookVerificationError

_HEADERS = ("webhook-id", "webhook-timestamp", "webhook-signature")


class FirmaInvalida(Exception):
    """La firma no es válida, faltan headers o no hay secreto configurado."""


def verificar_firma(cuerpo: bytes, headers) -> None:
    secreto = settings.PEY_WEBHOOK_SECRET
    if not secreto:
        raise FirmaInvalida("El secreto del webhook no está configurado.")

    cabeceras: dict[str, str] = {}
    for nombre in _HEADERS:
        valor = headers.get(nombre)
        if not valor:
            raise FirmaInvalida(f"Falta el header {nombre}.")
        cabeceras[nombre] = valor

    try:
        Webhook(secreto).verify(cuerpo, cabeceras, json_parse=False)
    except WebhookVerificationError as exc:
        raise FirmaInvalida("Firma inválida.") from exc
    except Exception as exc:
        # Secreto ilegible, cuerpo que no es texto o firma mal formada.
        raise FirmaInvalida("Firma inválida.") from exc
