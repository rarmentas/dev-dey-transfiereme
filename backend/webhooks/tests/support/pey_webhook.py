"""Fixture HTTP firmado para pruebas del webhook de pey (sin secretos reales)."""

import base64
import json
from datetime import datetime, timezone
from math import floor

from standardwebhooks import Webhook

SECRETO = "whsec_" + base64.b64encode(
    b"prueba-historia-1.5-no-es-secreto-real"
).decode()

RUTA = "/api/webhooks/pey/"


def encabezados(cuerpo: str, msg_id: str, cuando: datetime) -> dict[str, str]:
    firma = Webhook(SECRETO).sign(msg_id, cuando, cuerpo)
    marca = str(floor(cuando.replace(tzinfo=timezone.utc).timestamp()))
    return {
        "webhook-id": msg_id,
        "webhook-timestamp": marca,
        "webhook-signature": firma,
    }


def cuerpo_qr(
    *,
    transaction_id: str,
    codi_qr_id: str,
    amount: object = 25,
) -> str:
    return json.dumps(
        {
            "type": "codi.qr.payment_received",
            "amount": amount,
            "concept": "Transferencia",
            "transactionId": transaction_id,
            "codiQrId": codi_qr_id,
        },
        separators=(",", ":"),
    )


def post_firmado(
    client,
    cuerpo: str,
    msg_id: str,
    *,
    cuando: datetime | None = None,
    headers: dict[str, str] | None = None,
):
    cuando = cuando or datetime.now(timezone.utc)
    if headers is None:
        headers = encabezados(cuerpo, msg_id, cuando)
    return client.post(
        RUTA,
        data=cuerpo,
        content_type="application/json",
        headers=headers,
    )
