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
    preparacion = models.CharField(
        max_length=10, default="pendiente", choices=[
            ("pendiente", "Pendiente"), ("listo", "Listo"),
            ("entregado", "Entregado"),
        ],
    )
    listo_en = models.DateTimeField(null=True, blank=True)
    entregado_en = models.DateTimeField(null=True, blank=True)
    listo_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
        related_name="pedidos_listos",
    )
    entregado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
        related_name="pedidos_entregados",
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "pedido"
        verbose_name_plural = "pedidos"
        constraints = [
            models.CheckConstraint(
                condition=Q(preparacion__in=["pendiente", "listo", "entregado"]),
                name="pedido_preparacion_valida",
            ),
            models.CheckConstraint(
                condition=~Q(preparacion__in=["listo", "entregado"])
                | Q(listo_en__isnull=False, listo_por__isnull=False),
                name="pedido_listo_coherente",
            ),
            models.CheckConstraint(
                condition=~Q(preparacion="entregado") | Q(
                    entregado_en__isnull=False, entregado_por__isnull=False,
                    estado="cerrado",
                ),
                name="pedido_entregado_coherente",
            ),
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


class IntentoCobro(models.Model):
    """Intención durable y destino histórico de un cobro."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    origen = models.CharField(
        max_length=10, choices=[("pedido", "Pedido"), ("legado", "Legado")]
    )
    comercio = models.ForeignKey("ambito.Comercio", on_delete=models.PROTECT)
    pedido = models.ForeignKey(
        Pedido, null=True, blank=True, on_delete=models.PROTECT, related_name="intentos"
    )
    aceptacion = models.OneToOneField(
        Aceptacion,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="intento",
    )
    cotizacion = models.ForeignKey(
        Cotizacion, null=True, blank=True, on_delete=models.PROTECT
    )
    canal = models.CharField(
        max_length=20,
        choices=[("qr_venta", "QR de venta"), ("notificacion", "Notificación")],
    )
    estado = models.CharField(
        max_length=12,
        choices=[
            (v, v)
            for v in (
                "en_espera",
                "reservado",
                "enviando",
                "pendiente",
                "incierto",
                "rechazado",
                "vencido",
                "pagado",
                "descartado",
            )
        ],
    )
    version = models.PositiveIntegerField(default=1)
    importe_efectivo_centavos = models.BigIntegerField()
    demo_mode = models.BooleanField()
    politica_cobro_version = models.CharField(max_length=32)
    cuenta = models.ForeignKey(
        "ambito.CuentaCobro", null=True, blank=True, on_delete=models.PROTECT
    )
    pey_bank_account_id = models.CharField(max_length=26, blank=True)
    concepto = models.CharField(max_length=500)
    referencia = models.CharField(max_length=7, default="0")
    expiracion_s = models.PositiveSmallIntegerField()
    telefono_bancario = models.CharField(max_length=10, blank=True)
    clave_legado = models.CharField(max_length=128, blank=True)
    huella_legado = models.CharField(max_length=64, blank=True)
    token_envio = models.UUIDField(null=True, blank=True)
    envio_iniciado_en = models.DateTimeField(null=True, blank=True)
    enviado_en = models.DateTimeField(null=True, blank=True)
    request_id = models.CharField(max_length=64, blank=True)
    error = models.CharField(max_length=200, blank=True)
    motivo_descarte = models.CharField(max_length=60, blank=True)
    cobro = models.OneToOneField(
        "movimientos.Cobro",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="intento",
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["comercio"],
                condition=Q(
                    estado__in=["reservado", "enviando", "pendiente", "incierto"]
                ),
                name="intento_un_vivo_por_comercio",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        origen="pedido",
                        pedido__isnull=False,
                        aceptacion__isnull=False,
                        cotizacion__isnull=False,
                    )
                    | (
                        Q(
                            origen="legado",
                            pedido__isnull=True,
                            aceptacion__isnull=True,
                            cotizacion__isnull=True,
                        )
                        & ~Q(clave_legado="")
                    )
                ),
                name="intento_origen_coherente",
            ),
            models.UniqueConstraint(
                fields=["comercio", "clave_legado"],
                condition=~Q(clave_legado=""),
                name="intento_clave_legado_unica",
            ),
            models.CheckConstraint(
                condition=~Q(
                    estado__in=[
                        "reservado",
                        "enviando",
                        "pendiente",
                        "incierto",
                        "rechazado",
                        "vencido",
                        "pagado",
                    ]
                )
                | (Q(cuenta__isnull=False) & ~Q(pey_bank_account_id="")),
                name="intento_destino_fijado",
            ),
            models.CheckConstraint(
                condition=Q(
                    estado__in=[
                        "en_espera",
                        "reservado",
                        "enviando",
                        "pendiente",
                        "incierto",
                        "rechazado",
                        "vencido",
                        "pagado",
                        "descartado",
                    ]
                ),
                name="intento_estado_valido",
            ),
            models.CheckConstraint(
                condition=Q(canal__in=["qr_venta", "notificacion"]),
                name="intento_canal_valido",
            ),
            models.CheckConstraint(
                condition=Q(importe_efectivo_centavos__gt=0),
                name="intento_importe_positivo",
            ),
            models.CheckConstraint(
                condition=Q(demo_mode=False) | Q(importe_efectivo_centavos=1),
                name="intento_demo_un_centavo",
            ),
        ]

    def save(self, *args, **kwargs):
        campos = (
            "cuenta_id",
            "pey_bank_account_id",
            "importe_efectivo_centavos",
            "canal",
            "demo_mode",
            "politica_cobro_version",
        )
        if not self._state.adding:
            previo = (
                type(self).objects.filter(pk=self.pk).values("estado", *campos).first()
            )
            if (
                previo
                and previo["estado"] != "en_espera"
                and any(previo[campo] != getattr(self, campo) for campo in campos)
            ):
                raise ValueError("El destino histórico del intento es inmutable.")
        super().save(*args, **kwargs)


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
    intento = models.ForeignKey(
        IntentoCobro, null=True, blank=True, on_delete=models.PROTECT,
        related_name="eventos",
    )
    snapshot = models.JSONField()
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "evento de pedido"
        verbose_name_plural = "eventos de pedido"
        constraints = [
            models.UniqueConstraint(
                fields=["comercio", "secuencia_comercio"], name="evento_secuencia_unica"
            ),
            models.UniqueConstraint(
                fields=["intento", "tipo"], condition=Q(tipo__in=[
                    "cobro.en_espera", "cobro.pendiente", "cobro.incierto",
                    "cobro.rechazado", "cobro.descartado", "cobro.vencido",
                    "pago.confirmado",
                ]), name="evento_unico_por_intento_tipo",
            ),
            models.UniqueConstraint(
                fields=["pedido", "tipo"],
                condition=Q(tipo__in=["pedido.listo", "pedido.entregado"]),
                name="evento_unico_por_pedido_tipo",
            )
        ]
        indexes = [
            models.Index(
                fields=["comercio", "secuencia_comercio", "sesion_id"],
                name="evento_feed_idx",
            )
        ]
