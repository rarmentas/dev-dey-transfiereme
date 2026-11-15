"""Persistencia de pedidos, cotizaciones y eventos."""

import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from pedidos.contratos.v1 import EstadoPedido, Resolucion, TipoEvento


class Pedido(models.Model):
    class Estado(models.TextChoices):
        BORRADOR = "borrador", "Borrador"
        EN_REVISION = "en_revision", "En revisión"
        COTIZADO = "cotizado", "Cotizado"
        ACEPTADO = "aceptado", "Aceptado"
        CERRADO = "cerrado", "Cerrado"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    comercio = models.ForeignKey(
        "ambito.Comercio", on_delete=models.PROTECT, related_name="pedidos"
    )
    numero = models.PositiveIntegerField()
    instancia_id = models.CharField(max_length=64)
    sesion_id = models.CharField(max_length=64)
    conversacion_id = models.CharField(max_length=64)
    cliente_externo_id = models.CharField(max_length=128)
    mensaje_origen_id = models.UUIDField()
    message_key_origen = models.CharField(max_length=400)
    secuencia_conversacion_aplicada = models.BigIntegerField()
    version = models.PositiveIntegerField(default=1)
    estado = models.CharField(
        max_length=12,
        choices=Estado.choices,
        default=Estado.BORRADOR,
    )
    abierto = models.BooleanField(default=True)
    revision_vigente = models.PositiveIntegerField(null=True)
    ultima_revision = models.PositiveIntegerField(default=0)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "pedido"
        verbose_name_plural = "pedidos"
        constraints = [
            models.UniqueConstraint(
                fields=["comercio", "numero"], name="pedido_numero_unico"
            ),
            models.UniqueConstraint(
                fields=["comercio", "mensaje_origen_id"], name="pedido_origen_unico"
            ),
            models.UniqueConstraint(
                fields=["comercio", "instancia_id", "sesion_id", "conversacion_id"],
                condition=Q(abierto=True),
                name="pedido_un_abierto_por_conversacion",
            ),
            models.CheckConstraint(
                condition=Q(estado__in=[e.value for e in EstadoPedido]),
                name="pedido_estado_valido",
            ),
            models.CheckConstraint(
                condition=Q(version__gte=1), name="pedido_version_positiva"
            ),
            models.CheckConstraint(
                condition=(
                    Q(estado="cerrado", abierto=False)
                    | (~Q(estado="cerrado") & Q(abierto=True))
                ),
                name="pedido_cierre_coherente",
            ),
        ]
        indexes = [
            models.Index(
                fields=["comercio", "-actualizado_en"], name="pedido_lista_idx"
            ),
            models.Index(
                fields=["comercio", "conversacion_id"], name="pedido_conversacion_idx"
            ),
        ]


class RenglonPedido(models.Model):
    class EstadoResolucion(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        INCLUIDO = "incluido", "Incluido"
        EXCLUIDO = "excluido", "Excluido"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pedido = models.ForeignKey(
        Pedido, on_delete=models.CASCADE, related_name="renglones"
    )
    posicion = models.PositiveSmallIntegerField()
    texto_solicitado = models.CharField(max_length=500)
    cantidad_solicitada = models.DecimalField(max_digits=7, decimal_places=3, null=True)
    unidad_solicitada = models.CharField(max_length=30, null=True)
    descripcion = models.CharField(max_length=200, blank=True)
    cantidad = models.DecimalField(max_digits=7, decimal_places=3, null=True)
    unidad = models.CharField(max_length=30, blank=True)
    precio_unitario_centavos = models.BigIntegerField(null=True)
    resolucion = models.CharField(
        max_length=10,
        choices=EstadoResolucion.choices,
        default=EstadoResolucion.PENDIENTE,
    )
    motivo_exclusion = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = "renglón de pedido"
        verbose_name_plural = "renglones de pedido"
        constraints = [
            models.UniqueConstraint(
                fields=["pedido", "posicion"], name="renglon_posicion_unica"
            ),
            models.CheckConstraint(
                condition=Q(cantidad_solicitada__isnull=True)
                | Q(
                    cantidad_solicitada__gt=0,
                    cantidad_solicitada__lte=Decimal("9999.999"),
                ),
                name="renglon_cantidad_solicitada_valida",
            ),
            models.CheckConstraint(
                condition=Q(cantidad__isnull=True)
                | Q(cantidad__gt=0, cantidad__lte=Decimal("9999.999")),
                name="renglon_cantidad_valida",
            ),
            models.CheckConstraint(
                condition=Q(precio_unitario_centavos__isnull=True)
                | Q(precio_unitario_centavos__gt=0),
                name="renglon_precio_valido",
            ),
            models.CheckConstraint(
                condition=Q(resolucion__in=[e.value for e in Resolucion]),
                name="renglon_resolucion_valida",
            ),
            models.CheckConstraint(
                condition=~Q(resolucion="incluido")
                | (
                    Q(cantidad__isnull=False, precio_unitario_centavos__isnull=False)
                    & ~Q(descripcion="")
                ),
                name="renglon_incluido_completo",
            ),
            models.CheckConstraint(
                condition=~Q(resolucion="excluido") | ~Q(motivo_exclusion=""),
                name="renglon_excluido_motivo",
            ),
        ]


class Cotizacion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    comercio = models.ForeignKey("ambito.Comercio", on_delete=models.PROTECT)
    pedido = models.ForeignKey(
        Pedido, on_delete=models.PROTECT, related_name="cotizaciones"
    )
    revision = models.PositiveIntegerField()
    pedido_version_publicada = models.PositiveIntegerField()
    snapshot = models.JSONField()
    total_comercial_centavos = models.BigIntegerField()
    importe_efectivo_centavos = models.BigIntegerField()
    moneda = models.CharField(max_length=3, default="MXN")
    demo_mode = models.BooleanField()
    politica_cobro_version = models.CharField(max_length=32)
    token_resumen = models.CharField(max_length=32)
    publicada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL
    )
    publicada_en = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "cotización"
        verbose_name_plural = "cotizaciones"
        constraints = [
            models.UniqueConstraint(
                fields=["pedido", "revision"], name="cotizacion_revision_unica"
            ),
            models.UniqueConstraint(
                fields=["comercio", "token_resumen"], name="cotizacion_token_unico"
            ),
            models.CheckConstraint(
                condition=Q(
                    total_comercial_centavos__gt=0,
                    total_comercial_centavos__lte=100000000,
                ),
                name="cotizacion_total_valido",
            ),
            models.CheckConstraint(
                condition=Q(importe_efectivo_centavos__gt=0),
                name="cotizacion_importe_positivo",
            ),
            models.CheckConstraint(
                condition=Q(demo_mode=False) | Q(importe_efectivo_centavos=1),
                name="cotizacion_importe_demo",
            ),
            models.CheckConstraint(
                condition=Q(demo_mode=True)
                | Q(importe_efectivo_centavos=F("total_comercial_centavos")),
                name="cotizacion_importe_normal",
            ),
        ]


class Aceptacion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cotizacion = models.OneToOneField(
        Cotizacion, on_delete=models.PROTECT, related_name="aceptacion"
    )
    pedido = models.ForeignKey(Pedido, on_delete=models.PROTECT)
    comercio = models.ForeignKey("ambito.Comercio", on_delete=models.PROTECT)
    instancia_id = models.CharField(max_length=64)
    sesion_id = models.CharField(max_length=64)
    conversacion_id = models.CharField(max_length=64)
    cliente_externo_id = models.CharField(max_length=128)
    mensaje_consentimiento_id = models.UUIDField()
    salida_resumen_ref = models.CharField(max_length=200)
    token_resumen = models.CharField(max_length=32)
    importe_efectivo_centavos = models.BigIntegerField()
    demo_mode = models.BooleanField()
    politica_cobro_version = models.CharField(max_length=32)
    aceptada_en = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "aceptación"
        verbose_name_plural = "aceptaciones"
        constraints = [
            models.UniqueConstraint(
                fields=["comercio", "mensaje_consentimiento_id"],
                name="aceptacion_mensaje_unico",
            )
        ]


class ComandoNucleo(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    comercio = models.ForeignKey("ambito.Comercio", on_delete=models.PROTECT)
    operacion = models.CharField(max_length=40)
    command_key = models.CharField(max_length=128)
    hash_payload = models.CharField(max_length=64)
    pedido = models.ForeignKey(Pedido, null=True, on_delete=models.PROTECT)
    resultado = models.JSONField()
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "comando del núcleo"
        verbose_name_plural = "comandos del núcleo"
        constraints = [
            models.UniqueConstraint(
                fields=["comercio", "operacion", "command_key"],
                name="comando_clave_unica",
            )
        ]


class EventoPedido(models.Model):
    evento_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    comercio = models.ForeignKey("ambito.Comercio", on_delete=models.PROTECT)
    pedido = models.ForeignKey(Pedido, on_delete=models.PROTECT)
    secuencia_comercio = models.BigIntegerField()
    tipo = models.CharField(
        max_length=30, choices=[(e.value, e.value) for e in TipoEvento]
    )
    pedido_version = models.PositiveIntegerField()
    instancia_id = models.CharField(max_length=64)
    sesion_id = models.CharField(max_length=64)
    conversacion_id = models.CharField(max_length=64)
    cotizacion = models.ForeignKey(Cotizacion, null=True, on_delete=models.PROTECT)
    snapshot = models.JSONField()
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "evento de pedido"
        verbose_name_plural = "eventos de pedido"
        constraints = [
            models.UniqueConstraint(
                fields=["comercio", "secuencia_comercio"], name="evento_secuencia_unica"
            )
        ]
        indexes = [
            models.Index(
                fields=["comercio", "secuencia_comercio", "sesion_id"],
                name="evento_feed_idx",
            )
        ]
