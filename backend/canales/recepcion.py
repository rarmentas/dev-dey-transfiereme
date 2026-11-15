"""Persistencia idempotente de eventos entrantes."""

import hashlib
import json
import logging
from datetime import datetime, timezone

from django.conf import settings
from django.db import IntegrityError, transaction

from canales.models import ConversacionCanal, MensajeEntrante, SesionCanal

logger = logging.getLogger(__name__)


def _resultado_duplicado(anterior, huella):
    if anterior.hash_payload == huella:
        return "duplicado"
    logger.warning("Conflicto de id de mensaje WAHA: %s", anterior.pk)
    return "conflicto"


def recibir(datos: dict, entrega: str = "") -> str:
    if not isinstance(datos, dict):
        raise ValueError
    if datos.get("event") != "message":
        return "ignorado"
    payload = datos.get("payload")
    sesion_id = datos.get("session")
    if not isinstance(payload, dict) or not isinstance(sesion_id, str):
        raise ValueError
    proveedor, chat = payload.get("id"), payload.get("from")
    if not isinstance(proveedor, str) or not 0 < len(proveedor) <= 200:
        raise ValueError
    if not isinstance(chat, str) or not 0 < len(chat) <= 128:
        raise ValueError
    if not isinstance(payload.get("fromMe"), bool):
        raise ValueError
    if (
        payload["fromMe"]
        or chat.endswith(("@g.us", "@newsletter"))
        or chat == "status@broadcast"
    ):
        return "ignorado"
    sesion = SesionCanal.objects.filter(
        instancia_id=settings.WAHA_INSTANCIA, sesion_id=sesion_id, estado="activa"
    ).first()
    if not sesion:
        return "ignorado"
    huella = hashlib.sha256(
        json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()
    anterior = MensajeEntrante.objects.filter(
        instancia_id=sesion.instancia_id,
        sesion_id=sesion_id,
        id_mensaje_proveedor=proveedor,
    ).first()
    if anterior:
        return _resultado_duplicado(anterior, huella)
    media = (
        payload.get("_data", {}).get("mimetype", "")
        if isinstance(payload.get("_data"), dict)
        else ""
    )
    if isinstance(payload.get("media"), dict):
        media = payload["media"].get("mimetype", media)
    media = payload.get("mimetype", media)
    tipo = (
        "audio"
        if payload.get("hasMedia")
        and isinstance(media, str)
        and media.startswith("audio/")
        else "otro"
        if payload.get("hasMedia")
        else "texto"
    )
    texto = payload.get("body", "") if tipo == "texto" else ""
    if not isinstance(texto, str) or len(texto) > 4000:
        raise ValueError
    fecha = None
    try:
        if payload.get("timestamp") is not None:
            fecha = datetime.fromtimestamp(float(payload["timestamp"]), tz=timezone.utc)
    except (ValueError, TypeError, OverflowError, OSError):
        raise ValueError from None
    try:
        with transaction.atomic():
            conversacion, _ = ConversacionCanal.objects.get_or_create(
                sesion=sesion, chat_id=chat, defaults={"cliente_externo_id": chat}
            )
            conversacion = ConversacionCanal.objects.select_for_update().get(
                pk=conversacion.pk
            )
            conversacion.secuencia_recibida += 1
            MensajeEntrante.objects.create(
                conversacion=conversacion,
                instancia_id=sesion.instancia_id,
                sesion_id=sesion_id,
                id_mensaje_proveedor=proveedor,
                id_entrega_http=entrega[:200],
                hash_payload=huella,
                secuencia=conversacion.secuencia_recibida,
                tipo=tipo,
                texto=texto,
                timestamp_proveedor=fecha,
            )
            conversacion.save(update_fields=["secuencia_recibida"])
    except IntegrityError:
        anterior = MensajeEntrante.objects.filter(
            instancia_id=sesion.instancia_id,
            sesion_id=sesion_id,
            id_mensaje_proveedor=proveedor,
        ).first()
        if anterior is None:
            raise
        return _resultado_duplicado(anterior, huella)
    return "recibido"
