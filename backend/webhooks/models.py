"""Aviso de pey ya recibido. La llave de idempotencia es webhook-id."""

from django.db import models


class AvisoRecibido(models.Model):
    class Resultado(models.TextChoices):
        APLICADO = "aplicado", "Aplicado"
        DUPLICADO_TRANSACCION = "duplicado_transaccion", "Duplicado por transacción"
        SIN_COBRO = "sin_cobro", "Sin cobro"
        TRANSICION_INVALIDA = "transicion_invalida", "Transición inválida"
        TIPO_DESCONOCIDO = "tipo_desconocido", "Tipo desconocido"

    webhook_id = models.CharField(
        max_length=128,
        unique=True,
        verbose_name="webhook-id",
    )
    tipo = models.CharField(max_length=128, verbose_name="tipo")
    transaction_id = models.CharField(
        max_length=64,
        blank=True,
        verbose_name="id de transacción",
    )
    # Vacío solo dentro de la transacción, antes de conocer el resultado.
    # Al confirmar siempre queda uno de Resultado.
    resultado = models.CharField(
        max_length=32,
        blank=True,
        choices=Resultado.choices,
        verbose_name="resultado",
    )
    movimiento = models.ForeignKey(
        "movimientos.Movimiento",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="avisos_recibidos",
        verbose_name="movimiento",
    )
    recibido_en = models.DateTimeField(auto_now_add=True, verbose_name="recibido en")

    class Meta:
        verbose_name = "aviso recibido"
        verbose_name_plural = "avisos recibidos"
        ordering = ["-recibido_en", "-pk"]

    def __str__(self) -> str:
        return f"{self.webhook_id} ({self.resultado or 'sin resultado'})"
