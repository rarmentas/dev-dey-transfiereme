"""Entrega durable sin reintentos ciegos."""

import logging
import random
import time
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from canales.models import ConversacionCanal, SalidaCanal
from canales.waha import ErrorEnvio

logger = logging.getLogger(__name__)


def preparar(conversacion, causa, tipo, payload):
    return SalidaCanal.objects.get_or_create(
        causa=causa,
        destinatario=conversacion.cliente_externo_id,
        tipo=tipo,
        defaults={"conversacion": conversacion, "payload": payload},
    )[0]


def enviar(salida_id, transporte):
    with transaction.atomic():
        salida = (
            SalidaCanal.objects.select_for_update()
            .select_related("conversacion__sesion")
            .get(pk=salida_id)
        )
        if salida.estado != "preparada":
            return
        salida.estado = "enviando"
        salida.envio_iniciado_en = timezone.now()
        salida.intentos += 1
        salida.save(update_fields=["estado", "envio_iniciado_en", "intentos"])
    sesion_id = salida.conversacion.sesion.sesion_id
    chat_id = salida.conversacion.chat_id
    escribiendo = salida.payload.get("escribiendo") is True
    iniciar = getattr(transporte, "iniciar_escritura", None) if escribiendo else None
    detener = getattr(transporte, "detener_escritura", None) if escribiendo else None
    try:
        if callable(iniciar):
            try:
                iniciar(sesion_id, chat_id)
            except Exception as exc:
                logger.warning("presencia_escribiendo_error tipo=%s", type(exc).__name__)
            time.sleep(random.uniform(3, 6))
        proveedor = transporte.enviar_texto(
            sesion_id,
            chat_id,
            salida.payload["texto"],
        )
        if not isinstance(proveedor, str) or not proveedor or len(proveedor) > 200:
            raise ErrorEnvio()
    except Exception as exc:
        estado = (
            "fallida" if isinstance(exc, ErrorEnvio) and exc.definitivo else "incierta"
        )
        SalidaCanal.objects.filter(pk=salida.pk, estado="enviando").update(
            estado=estado, error="Error de transporte"
        )
        return
    finally:
        if callable(detener):
            try:
                detener(sesion_id, chat_id)
            except Exception as exc:
                logger.warning("presencia_pausada_error tipo=%s", type(exc).__name__)
    with transaction.atomic():
        salida = SalidaCanal.objects.select_for_update().get(pk=salida.pk)
        if salida.estado != "enviando":
            return
        salida.estado = "enviada"
        salida.id_proveedor = proveedor
        salida.enviado_en = timezone.now()
        salida.save(update_fields=["estado", "id_proveedor", "enviado_en"])
        if salida.tipo == "cotizacion_resumen":
            ConversacionCanal.objects.filter(pk=salida.conversacion_id).update(
                cotizacion_id_enviada=salida.payload["cotizacion_id"],
                token_enviado=salida.payload["token_resumen"],
            )


def recuperar_abandonadas():
    return SalidaCanal.objects.filter(
        estado="enviando", envio_iniciado_en__lt=timezone.now() - timedelta(seconds=60)
    ).update(estado="incierta", error="Envío sin confirmación")
