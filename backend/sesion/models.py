from django.db import models


class CodigoCorreo(models.Model):
    class Proposito(models.TextChoices):
        ALTA = "alta", "Alta de cuenta"
        OLVIDO = "olvido", "Olvido de contraseña"

    correo = models.EmailField(max_length=254)
    proposito = models.CharField(max_length=10, choices=Proposito.choices)
    codigo_hash = models.CharField(max_length=128)
    contrasena_hash = models.CharField(max_length=128, blank=True, default="")
    expira_en = models.DateTimeField()
    usado_en = models.DateTimeField(null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "código por correo"
        verbose_name_plural = "códigos por correo"
        indexes = [
            models.Index(
                fields=["correo", "proposito", "usado_en"],
                # Mismo nombre que en 0001_codigocorreo: sin migración pendiente.
                name="sesion_codi_correo_7f0e8e_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["correo", "proposito"],
                condition=models.Q(usado_en__isnull=True),
                name="sesion_codigocorreo_vigente_unico",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.correo} ({self.proposito})"
