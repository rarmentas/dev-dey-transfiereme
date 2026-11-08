"""Movimiento que ve el vendedor. No llama a pey ni a la red."""

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

    # pagado y vencido son terminales. vencido → pagado se rechaza: la
    # pregunta de producto sigue abierta (aceptar, rechazar o registrar
    # aparte un aviso tardío). No se acepta el pago ni se registra aparte.
    _TRANSICIONES = {
        Estado.PENDIENTE: frozenset({Estado.PAGADO, Estado.VENCIDO}),
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
    ]

    def __str__(self) -> str:
        return f"{self.concepto_visible or self.concepto} ({self.estado})"

    def save(self, *args, **kwargs):
        if self._state.adding and not self.concepto_visible:
            self.concepto_visible = self.concepto
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
            filas = (
                type(self)
                .objects.filter(pk=self.pk, estado=origen)
                .update(estado=nuevo, actualizado_en=timezone.now())
            )
            if filas != 1:
                raise TransicionInvalida(
                    f"Transición inválida: el estado ya no es {origen}."
                )
        self.estado = nuevo
        self.refresh_from_db(fields=["estado", "actualizado_en"])

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
