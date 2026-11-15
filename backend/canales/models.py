"""Persistencia del canal de mensajería."""

import uuid

from django.db import models
from django.db.models import Q
from django.utils import timezone


class SesionCanal(models.Model):
    class Estado(models.TextChoices):
        ACTIVA = "activa", "Activa"
        INACTIVA = "inactiva", "Inactiva"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    instancia_id = models.CharField(max_length=64)
    sesion_id = models.CharField(max_length=64)
    comercio = models.ForeignKey("ambito.Comercio", on_delete=models.PROTECT)
    estado = models.CharField(
        max_length=10, choices=Estado.choices, default=Estado.ACTIVA
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "sesión de canal"
        verbose_name_plural = "sesiones de canal"
        constraints = [
            models.UniqueConstraint(
                fields=["instancia_id", "sesion_id"], name="canal_sesion_unica"
            )
        ]


class ConversacionCanal(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sesion = models.ForeignKey(SesionCanal, on_delete=models.PROTECT)
    chat_id = models.CharField(max_length=128)
    cliente_externo_id = models.CharField(max_length=128)
    secuencia_recibida = models.BigIntegerField(default=0)
    pedido_id_actual = models.UUIDField(null=True)
    cotizacion_id_enviada = models.UUIDField(null=True)
    token_enviado = models.CharField(max_length=32, blank=True)
    lease_token = models.UUIDField(null=True)
    lease_hasta = models.DateTimeField(null=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "conversación de canal"
        verbose_name_plural = "conversaciones de canal"
        constraints = [
            models.UniqueConstraint(
                fields=["sesion", "chat_id"], name="canal_chat_unico"
            )
        ]


class MensajeEntrante(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        PROCESADO = "procesado", "Procesado"
        REINTENTABLE = "reintentable", "Reintentable"
        FALLIDO = "fallido", "Fallido"
        IGNORADO = "ignorado", "Ignorado"

    class Tipo(models.TextChoices):
        TEXTO = "texto", "Texto"
        AUDIO = "audio", "Audio"
        OTRO = "otro", "Otro"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversacion = models.ForeignKey(ConversacionCanal, on_delete=models.PROTECT)
    instancia_id = models.CharField(max_length=64)
    sesion_id = models.CharField(max_length=64)
    id_mensaje_proveedor = models.CharField(max_length=200)
    id_entrega_http = models.CharField(max_length=200, blank=True)
    hash_payload = models.CharField(max_length=64)
    secuencia = models.BigIntegerField()
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    texto = models.TextField(blank=True)
    timestamp_proveedor = models.DateTimeField(null=True)
    recibido_en = models.DateTimeField(default=timezone.now)
    estado = models.CharField(
        max_length=12, choices=Estado.choices, default=Estado.PENDIENTE
    )
    intentos = models.PositiveSmallIntegerField(default=0)
    proximo_intento_en = models.DateTimeField(null=True)
    error = models.CharField(max_length=200, blank=True)
    procesado_en = models.DateTimeField(null=True)

    class Meta:
        verbose_name = "mensaje entrante"
        verbose_name_plural = "mensajes entrantes"
        constraints = [
            models.UniqueConstraint(
                fields=["instancia_id", "sesion_id", "id_mensaje_proveedor"],
                name="canal_mensaje_unico",
            ),
            models.UniqueConstraint(
                fields=["conversacion", "secuencia"], name="canal_secuencia_unica"
            ),
        ]
        indexes = [
            models.Index(
                fields=["conversacion", "secuencia"],
                condition=Q(estado__in=["pendiente", "reintentable"]),
                name="canal_mensajes_pendientes",
            )
        ]


class SalidaCanal(models.Model):
    class Estado(models.TextChoices):
        PREPARADA = "preparada", "Preparada"
        ENVIANDO = "enviando", "Enviando"
        ENVIADA = "enviada", "Enviada"
        INCIERTA = "incierta", "Incierta"
        FALLIDA = "fallida", "Fallida"

    class Tipo(models.TextChoices):
        RESPUESTA = "respuesta", "Respuesta"
        COTIZACION = "cotizacion_resumen", "Cotización"
        AVISO = "aviso", "Aviso"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversacion = models.ForeignKey(ConversacionCanal, on_delete=models.PROTECT)
    causa = models.CharField(max_length=160)
    destinatario = models.CharField(max_length=128)
    tipo = models.CharField(max_length=30, choices=Tipo.choices)
    payload = models.JSONField()
    estado = models.CharField(
        max_length=10, choices=Estado.choices, default=Estado.PREPARADA
    )
    id_proveedor = models.CharField(max_length=200, blank=True)
    envio_iniciado_en = models.DateTimeField(null=True)
    enviado_en = models.DateTimeField(null=True)
    intentos = models.PositiveSmallIntegerField(default=0)
    error = models.CharField(max_length=200, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "salida de canal"
        verbose_name_plural = "salidas de canal"
        constraints = [
            models.UniqueConstraint(
                fields=["causa", "destinatario", "tipo"], name="canal_salida_unica"
            ),
            models.CheckConstraint(
                condition=~Q(estado="enviada") | ~Q(id_proveedor=""),
                name="canal_salida_ack_requerido",
            ),
        ]
        indexes = [
            models.Index(
                fields=["creado_en"],
                condition=Q(estado="preparada"),
                name="canal_salidas_preparadas",
            )
        ]


class CursorCanal(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    consumidor = models.CharField(max_length=32)
    sesion = models.ForeignKey(SesionCanal, on_delete=models.PROTECT)
    cursor = models.TextField(blank=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "cursor de canal"
        verbose_name_plural = "cursores de canal"
        constraints = [
            models.UniqueConstraint(
                fields=["consumidor", "sesion"], name="canal_cursor_unico"
            )
        ]


class LatidoCanal(models.Model):
    proceso = models.CharField(max_length=32, primary_key=True)
    ultimo_ciclo = models.DateTimeField()
    ciclos = models.BigIntegerField(default=0)

    class Meta:
        verbose_name = "latido de canal"
        verbose_name_plural = "latidos de canal"


class TrabajoAudio(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        PROCESANDO = "procesando", "Procesando"
        LISTO = "listo", "Listo"
        FALLIDO = "fallido", "Fallido"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    mensaje = models.OneToOneField(MensajeEntrante, on_delete=models.PROTECT)
    estado = models.CharField(
        max_length=10, choices=Estado.choices, default="pendiente"
    )
    media_url = models.CharField(max_length=500, blank=True)
    mimetype = models.CharField(max_length=80, blank=True)
    duracion_declarada_s = models.DecimalField(
        max_digits=6, decimal_places=1, null=True
    )
    intentos = models.PositiveSmallIntegerField(default=0)
    lease_token = models.UUIDField(null=True)
    lease_hasta = models.DateTimeField(null=True)
    vence_en = models.DateTimeField()
    iniciado_en = models.DateTimeField(null=True)
    terminado_en = models.DateTimeField(null=True)
    transcripcion = models.TextField(blank=True)
    motivo = models.CharField(max_length=40, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(estado__in=["pendiente", "procesando", "listo", "fallido"]),
                name="trabajo_estado_valido",
            ),
            models.CheckConstraint(
                condition=~Q(estado="listo") | ~Q(transcripcion=""),
                name="trabajo_listo_con_texto",
            ),
        ]
        indexes = [
            models.Index(
                fields=["vence_en"],
                condition=Q(estado__in=["pendiente", "procesando"]),
                name="trabajo_audio_vigente",
            )
        ]
