"""Cobro enviado a pey y movimiento que ve el vendedor. No llama a pey ni a la red."""

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from ambito.models import Comercio
from movimientos.exceptions import TransicionInvalida


class Movimiento(models.Model):
    class Canal(models.TextChoices):
        QR_GENERAL = "qr_general", "QR general"
        QR_VENTA = "qr_venta", "QR de venta"
        NOTIFICACION = "notificacion", "Notificación"

    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        PAGADO = "pagado", "Pagado"
        VENCIDO = "vencido", "Vencido"

    class Origen(models.TextChoices):
        ORIGEN_PEY = "origen_pey", "Origen pey"
        ORIGEN_DESARROLLO = "origen_desarrollo", "Origen desarrollo"

    # pagado no sale de ahí. vencido → pagado acepta un aviso tardío:
    # el pago real no se pierde aunque el cobro ya se haya marcado vencido.
    _TRANSICIONES = {
        Estado.PENDIENTE: frozenset({Estado.PAGADO, Estado.VENCIDO}),
        Estado.VENCIDO: frozenset({Estado.PAGADO}),
    }

    # PROTECT: borrar el comercio no puede llevarse el historial de cobros.
    comercio = models.ForeignKey(
        Comercio,
        on_delete=models.PROTECT,
        related_name="movimientos",
        verbose_name="comercio",
    )
    monto = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="monto")
    concepto = models.CharField(max_length=500, verbose_name="concepto")
    concepto_visible = models.CharField(
        max_length=500,
        blank=True,
        default="",
        verbose_name="concepto visible",
    )
    canal = models.CharField(
        max_length=20,
        choices=Canal.choices,
        verbose_name="canal",
    )
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.PENDIENTE,
        verbose_name="estado",
    )
    origen = models.CharField(
        max_length=32,
        choices=Origen.choices,
        verbose_name="origen",
    )
    # Nullable: los movimientos de la 1.3 no tienen cobro. PROTECT para no
    # borrar el cobro si ya hay historial.
    cobro = models.ForeignKey(
        "Cobro",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="movimientos",
        verbose_name="cobro",
    )
    # transactionId del pago que lo marcó pagado. En el QR general cada pago
    # es un movimiento nuevo. Vacío se guarda como NULL para que la unicidad
    # permita varios movimientos todavía sin pago.
    pey_transaction_id = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        unique=True,
        verbose_name="id de transacción en pey",
    )
    # Instante del pago. El día del tablero sale de aquí en
    # America/Mexico_City. La constraint lo exige si y solo si está pagado.
    pagado_en = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="pagado en",
    )
    creado_en = models.DateTimeField(auto_now_add=True, verbose_name="creado en")
    actualizado_en = models.DateTimeField(auto_now=True, verbose_name="actualizado en")

    class Meta:
        verbose_name = "movimiento"
        verbose_name_plural = "movimientos"
        ordering = ["-creado_en", "-pk"]

    # Canal/Estado/Origen no son visibles dentro de class Meta; se asignan aquí,
    # antes de que Django lea las opciones.
    Meta.constraints = [
        models.CheckConstraint(
            condition=models.Q(monto__gt=0),
            name="movimiento_monto_mayor_a_cero",
        ),
        models.CheckConstraint(
            condition=models.Q(canal__in=Canal.values),
            name="movimiento_canal_valido",
        ),
        models.CheckConstraint(
            condition=models.Q(estado__in=Estado.values),
            name="movimiento_estado_valido",
        ),
        models.CheckConstraint(
            condition=models.Q(origen__in=Origen.values),
            name="movimiento_origen_valido",
        ),
        models.CheckConstraint(
            condition=(
                models.Q(estado=Estado.PAGADO, pagado_en__isnull=False)
                | (
                    ~models.Q(estado=Estado.PAGADO)
                    & models.Q(pagado_en__isnull=True)
                )
            ),
            name="movimiento_pagado_en_solo_si_pagado",
        ),
    ]

    def __str__(self) -> str:
        return f"{self.concepto_visible or self.concepto} ({self.estado})"

    def save(self, *args, **kwargs):
        if self.pey_transaction_id == "":
            self.pey_transaction_id = None
        if self._state.adding and not self.concepto_visible:
            self.concepto_visible = self.concepto
        # El QR general nace pagado y no pasa por cambiar_estado. Sin este
        # instante la constraint rechaza el INSERT.
        if (
            self._state.adding
            and self.estado == self.Estado.PAGADO
            and self.pagado_en is None
        ):
            self.pagado_en = timezone.now()
        # El canal (y el comercio) tienen que ser los del cobro. Un
        # CheckConstraint no cruza tablas; esta lectura por llave es barata.
        self._exigir_coherencia_con_cobro()
        if not self._state.adding and self._escribe_estado(kwargs.get("update_fields")):
            estado_en_bd = self._estado_persistido()
            if estado_en_bd is not None and estado_en_bd != self.estado:
                raise TransicionInvalida(
                    "El estado de un movimiento existente solo cambia con cambiar_estado()."
                )
        super().save(*args, **kwargs)

    def cambiar_estado(self, nuevo: str) -> None:
        """Único camino para cambiar `estado`. Atómico respecto al estado actual."""
        if self.pk is None:
            raise TransicionInvalida("El movimiento todavía no está persistido.")
        with transaction.atomic():
            bloqueado = type(self).objects.select_for_update().get(pk=self.pk)
            origen = bloqueado.estado
            if nuevo not in self._TRANSICIONES.get(origen, frozenset()):
                raise TransicionInvalida(f"Transición inválida: {origen} → {nuevo}.")
            ahora = timezone.now()
            campos = {"estado": nuevo, "actualizado_en": ahora}
            # Mismo UPDATE condicional: pagado y su instante quedan juntos.
            if nuevo == self.Estado.PAGADO:
                campos["pagado_en"] = ahora
            filas = (
                type(self)
                .objects.filter(pk=self.pk, estado=origen)
                .update(**campos)
            )
            if filas != 1:
                raise TransicionInvalida(
                    f"Transición inválida: el estado ya no es {origen}."
                )
        self.estado = nuevo
        self.refresh_from_db(fields=["estado", "actualizado_en", "pagado_en"])

    def _exigir_coherencia_con_cobro(self) -> None:
        if self.cobro_id is None:
            return
        cobro = self.cobro
        if self.canal != cobro.canal:
            raise ValueError(
                "El canal del movimiento tiene que coincidir con el del cobro."
            )
        if self.comercio_id != cobro.comercio_id:
            raise ValueError(
                "El comercio del movimiento tiene que ser el del cobro."
            )

    def _estado_persistido(self) -> str | None:
        if self.pk is None:
            return None
        return (
            type(self)
            .objects.filter(pk=self.pk)
            .values_list("estado", flat=True)
            .first()
        )

    @staticmethod
    def _escribe_estado(update_fields) -> bool:
        return update_fields is None or "estado" in update_fields


class Cobro(models.Model):
    """Instancia enviada a pey: QR general, QR de venta o notificación.

    El comercio se fija al crear el cobro en el servidor y no se lee del aviso.
    """

    # ULID de pey son 26 caracteres; el IDC de Banxico cabe holgado en 64.
    _LARGO_ID_PEY = 64

    comercio = models.ForeignKey(
        Comercio,
        on_delete=models.PROTECT,
        related_name="cobros",
        verbose_name="comercio",
    )
    canal = models.CharField(
        max_length=20,
        choices=Movimiento.Canal.choices,
        verbose_name="canal",
    )
    # qr_general es monto abierto (0, amount: 0 en pey). Los otros exigen > 0.
    monto = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="monto")
    concepto = models.CharField(max_length=500, verbose_name="concepto")
    # El QR general no vence.
    vence_en = models.DateTimeField(null=True, blank=True, verbose_name="vence en")
    creado_en = models.DateTimeField(auto_now_add=True, verbose_name="creado en")
    pey_qr_id = models.CharField(
        max_length=_LARGO_ID_PEY,
        null=True,
        blank=True,
        unique=True,
        verbose_name="id de QR en pey",
    )
    pey_transaction_id = models.CharField(
        max_length=_LARGO_ID_PEY,
        null=True,
        blank=True,
        unique=True,
        verbose_name="id de transacción en pey",
    )
    qr_string = models.CharField(
        max_length=4096,
        blank=True,
        default="",
        verbose_name="cadena del QR",
    )
    # ULID de la cuenta ACTIVE a la que pey abonó este cobro. Vacío si se
    # creó sin bankAccountId (desarrollo o un QR anterior al arreglo).
    pey_bank_account_id = models.CharField(
        max_length=26,
        blank=True,
        default="",
        verbose_name="id de cuenta en pey",
    )

    class Meta:
        verbose_name = "cobro"
        verbose_name_plural = "cobros"
        ordering = ["-creado_en", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(canal__in=Movimiento.Canal.values),
                name="cobro_canal_valido",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(canal=Movimiento.Canal.QR_GENERAL, monto=0)
                    | models.Q(
                        canal__in=[
                            Movimiento.Canal.QR_VENTA,
                            Movimiento.Canal.NOTIFICACION,
                        ],
                        monto__gt=0,
                    )
                ),
                name="cobro_monto_segun_canal",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        canal__in=[
                            Movimiento.Canal.QR_GENERAL,
                            Movimiento.Canal.QR_VENTA,
                        ],
                        pey_qr_id__isnull=False,
                        pey_transaction_id__isnull=True,
                    )
                    | models.Q(
                        canal=Movimiento.Canal.NOTIFICACION,
                        pey_qr_id__isnull=True,
                        pey_transaction_id__isnull=False,
                    )
                ),
                name="cobro_ids_pey_segun_canal",
            ),
            models.UniqueConstraint(
                fields=["comercio"],
                condition=models.Q(canal=Movimiento.Canal.QR_GENERAL),
                name="cobro_qr_general_unico_por_comercio",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.concepto} ({self.canal})"

    def save(self, *args, **kwargs):
        if self.pey_qr_id == "":
            self.pey_qr_id = None
        if self.pey_transaction_id == "":
            self.pey_transaction_id = None
        if self.canal in (
            Movimiento.Canal.QR_GENERAL,
            Movimiento.Canal.QR_VENTA,
        ) and not self.qr_string.strip():
            raise ValidationError("Los cobros por QR requieren qr_string.")
        super().save(*args, **kwargs)
