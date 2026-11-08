from django.conf import settings
from django.db import models


class Comercio(models.Model):
    nombre = models.CharField(max_length=200)
    semilla_active_dev = models.BooleanField(
        default=False,
        help_text=(
            "Marca de la semilla local de desarrollo. No autoriza cobros "
            "ni cuenta como cuenta ACTIVE en pey."
        ),
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "comercio"
        verbose_name_plural = "comercios"
        ordering = ["nombre"]

    def __str__(self) -> str:
        return self.nombre


class Membresia(models.Model):
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="membresia",
        verbose_name="usuario",
    )
    comercio = models.ForeignKey(
        Comercio,
        on_delete=models.CASCADE,
        related_name="membresias",
        verbose_name="comercio",
    )

    class Meta:
        verbose_name = "membresía"
        verbose_name_plural = "membresías"

    def __str__(self) -> str:
        return f"{self.usuario} → {self.comercio}"
