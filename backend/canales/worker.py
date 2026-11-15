"""Ciclo del trabajador del canal."""

import uuid
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone
from django.utils.module_loading import import_string

from canales import audio
from canales.avisos import procesar_avisos
from canales.conversacion import contexto, procesar_mensaje
from canales.models import ConversacionCanal, LatidoCanal, MensajeEntrante, SalidaCanal
from canales.salidas import enviar, recuperar_abandonadas
from config.modo import modo_de_comercio
from pedidos.contratos.v1 import CONTRATO_VERSION
from pedidos.fabrica import obtener_lector, obtener_nucleo


def reclamar(excluir=()):
    ahora = timezone.now()
    with transaction.atomic():
        candidatos = (
            ConversacionCanal.objects.filter(
                Q(lease_hasta__isnull=True) | Q(lease_hasta__lt=ahora),
                mensajeentrante__estado__in=["pendiente", "reintentable"],
            )
            .order_by("creado_en")
            .select_for_update(skip_locked=True, of=("self",))
        )
        for conversacion in candidatos:
            mensaje = (
                MensajeEntrante.objects.filter(
                    conversacion=conversacion, estado__in=["pendiente", "reintentable"]
                )
                .order_by("secuencia")
                .first()
            )
            if mensaje and audio.esperando(mensaje, ahora):
                continue
            if (
                mensaje
                and mensaje.pk not in excluir
                and (
                    not mensaje.proximo_intento_en
                    or mensaje.proximo_intento_en <= ahora
                )
            ):
                token = uuid.uuid4()
                conversacion.lease_token = token
                conversacion.lease_hasta = ahora + timedelta(seconds=60)
                conversacion.save(update_fields=["lease_token", "lease_hasta"])
                return conversacion.pk, token, mensaje.pk
    return None


_nucleo_stub = None


def ciclo():
    global _nucleo_stub
    lector = obtener_lector()
    if settings.NUCLEO_ADAPTADOR.strip().lower() == "stub" and _nucleo_stub:
        nucleo = _nucleo_stub
    else:
        nucleo = obtener_nucleo()
        if nucleo.ES_SIMULACION:
            _nucleo_stub = nucleo
    audio.expirar_trabajos()
    recuperar_abandonadas()
    vistos = set()
    while True:
        reclamo = reclamar(vistos)
        if not reclamo:
            break
        conversacion_id, token, mensaje_id = reclamo
        vistos.add(mensaje_id)
        try:
            mensaje = MensajeEntrante.objects.select_related(
                "conversacion__sesion"
            ).get(pk=mensaje_id)
            procesar_mensaje(mensaje, nucleo, lector, timezone.now())
        finally:
            ConversacionCanal.objects.filter(
                pk=conversacion_id, lease_token=token
            ).update(lease_token=None, lease_hasta=None)
    procesar_avisos(nucleo, lector)
    transporte = import_string(settings.CANAL_TRANSPORTE)()
    for salida in (
        SalidaCanal.objects.filter(estado="preparada")
        .select_related("conversacion__sesion")
        .order_by("creado_en", "id")
    ):
        if salida.tipo == "cotizacion_resumen":
            respuesta = nucleo.consultar_pedido(
                contexto(salida.conversacion),
                contrato_version=CONTRATO_VERSION,
                pedido_id=salida.payload["pedido_id"],
            )
            if not respuesta.ok:
                if not respuesta.error.retryable:
                    SalidaCanal.objects.filter(pk=salida.pk, estado="preparada").update(
                        estado="fallida", error="Cotización no disponible"
                    )
                continue
            cot = respuesta.data["pedido"].cotizacion
            if (
                not cot
                or cot.id != salida.payload["cotizacion_id"]
                or (cot.demo_mode, cot.politica_cobro_version)
                != modo_de_comercio(salida.conversacion.sesion.comercio_id)
            ):
                SalidaCanal.objects.filter(pk=salida.pk, estado="preparada").update(
                    estado="fallida", error="Cotización obsoleta"
                )
                continue
        enviar(salida.pk, transporte)
    LatidoCanal.objects.get_or_create(
        proceso="procesar_canal", defaults={"ultimo_ciclo": timezone.now()}
    )
    LatidoCanal.objects.filter(proceso="procesar_canal").update(
        ultimo_ciclo=timezone.now(), ciclos=F("ciclos") + 1
    )
