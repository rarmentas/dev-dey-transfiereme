"""Cola y procesamiento de audio con lease."""

import os
import shutil
import tempfile
import time
import uuid
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from canales import audio_conversion, media
from canales.models import LatidoCanal, MensajeEntrante, TrabajoAudio
from canales.stt import SttTimeout


def crear_trabajo(mensaje, payload, mimetype):
    datos = payload.get("_data") if isinstance(payload.get("_data"), dict) else {}
    multimedia = payload.get("media") if isinstance(payload.get("media"), dict) else {}
    url = multimedia.get("url") or payload.get("mediaUrl") or ""
    url = url if isinstance(url, str) and len(url) <= 500 else ""
    try:
        duracion = Decimal(str(datos.get("seconds")))
        if not duracion.is_finite() or duracion < 0 or duracion > 9999:
            duracion = None
    except (InvalidOperation, ValueError):
        duracion = None
    TrabajoAudio.objects.create(
        mensaje=mensaje,
        media_url=url,
        mimetype=mimetype[:80],
        duracion_declarada_s=duracion,
        vence_en=mensaje.recibido_en + timedelta(seconds=settings.STT_PRESUPUESTO_S),
        estado="pendiente" if url else "fallido",
        motivo="" if url else "sin_media",
        terminado_en=None if url else timezone.now(),
    )


def esperando(mensaje, ahora):
    return TrabajoAudio.objects.filter(
        mensaje=mensaje, estado__in=["pendiente", "procesando"], vence_en__gt=ahora
    ).exists()


def expirar_trabajos():
    ahora = timezone.now()
    vencidos = TrabajoAudio.objects.filter(
        Q(vence_en__lte=ahora) | Q(estado="procesando", lease_hasta__lte=ahora),
        estado__in=["pendiente", "procesando"],
    )
    return vencidos.update(
        estado="fallido",
        motivo="stt_timeout",
        lease_token=None,
        lease_hasta=None,
        terminado_en=ahora,
    )


def reclamar_trabajo():
    ahora = timezone.now()
    with transaction.atomic():
        trabajo = (
            TrabajoAudio.objects.select_for_update(skip_locked=True)
            .filter(estado="pendiente", vence_en__gt=ahora + timedelta(seconds=2))
            .order_by("creado_en")
            .first()
        )
        if not trabajo:
            return None
        trabajo.estado = "procesando"
        trabajo.intentos += 1
        trabajo.lease_token = uuid.uuid4()
        trabajo.lease_hasta = min(trabajo.vence_en, ahora + timedelta(seconds=45))
        trabajo.iniciado_en = ahora
        trabajo.save(
            update_fields=[
                "estado",
                "intentos",
                "lease_token",
                "lease_hasta",
                "iniciado_en",
            ]
        )
        return trabajo


def completar(trabajo, texto="", motivo=""):
    ahora = timezone.now()
    texto = texto.strip()[:4000]
    if not texto and not motivo:
        motivo = "stt_vacio"
    with transaction.atomic():
        actualizado = TrabajoAudio.objects.filter(
            pk=trabajo.pk,
            lease_token=trabajo.lease_token,
            estado="procesando",
            vence_en__gt=ahora,
            lease_hasta__gt=ahora,
        ).update(
            estado="fallido" if motivo else "listo",
            motivo=motivo,
            transcripcion=texto if not motivo else "",
            terminado_en=ahora,
            lease_token=None,
            lease_hasta=None,
        )
        if actualizado and not motivo:
            MensajeEntrante.objects.filter(pk=trabajo.mensaje_id).update(texto=texto)
        return bool(actualizado)


def barrer_temporales():
    limite = time.time() - 86400
    for ruta in Path(tempfile.gettempdir()).glob("stt-*"):
        try:
            if (
                ruta.is_dir()
                and not ruta.is_symlink()
                and ruta.stat().st_mtime < limite
            ):
                shutil.rmtree(ruta)
        except OSError:
            continue


def procesar(
    trabajo, transcriptor, descarga=media.descargar_acotado, conversion=audio_conversion
):
    deadline = time.monotonic() + max(
        0, (trabajo.vence_en - timezone.now()).total_seconds()
    )

    def restante(maximo):
        segundos = min(maximo, deadline - time.monotonic())
        if segundos <= 0:
            raise SttTimeout
        return segundos

    try:
        if trabajo.duracion_declarada_s and (
            trabajo.duracion_declarada_s > settings.WHATSAPP_AUDIO_MAX_SEGUNDOS
        ):
            raise media.ErrorAudio("demasiado_largo")
        with tempfile.TemporaryDirectory(prefix="stt-") as directorio:
            os.chmod(directorio, 0o700)
            origen = Path(directorio) / "media"
            wav = Path(directorio) / "audio.wav"
            descarga(trabajo.media_url, origen, restante(15))
            conversion.inspeccionar(origen, restante(10))
            conversion.a_wav_16k(origen, wav, restante(10))
            muestras = conversion.validar_wav(wav)
            texto = transcriptor.transcribir(muestras, deadline)
            restante(45)
            return completar(trabajo, texto=texto)
    except media.ErrorAudio as exc:
        return completar(trabajo, motivo=exc.motivo)
    except SttTimeout:
        return completar(trabajo, motivo="stt_timeout")
    except Exception:
        return completar(trabajo, motivo="formato")


def ciclo(transcriptor):
    expirar_trabajos()
    while trabajo := reclamar_trabajo():
        procesar(trabajo, transcriptor)
    LatidoCanal.objects.get_or_create(
        proceso="procesar_audio", defaults={"ultimo_ciclo": timezone.now()}
    )
    LatidoCanal.objects.filter(pk="procesar_audio").update(
        ultimo_ciclo=timezone.now(), ciclos=F("ciclos") + 1
    )
