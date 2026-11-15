import uuid

from django.conf import settings
from django.db import models


class Comercio(models.Model):
    class PeyCodiStatus(models.TextChoices):
        PENDING = "pending", "Pendiente"
        ACTIVE = "active", "Activa"

    nombre = models.CharField(max_length=200)
    es_demo = models.BooleanField(default=False, help_text="Designado por operador.")
    agente_pedidos_habilitado = models.BooleanField(default=False)
    semilla_active_dev = models.BooleanField(
        default=False,
        help_text=(
            "Marca de la semilla local de desarrollo. No autoriza cobros "
            "ni cuenta como cuenta ACTIVE en pey."
        ),
    )
    clabe = models.CharField(
        max_length=18,
        blank=True,
        default="",
        verbose_name="CLABE",
    )
    pey_codi_status = models.CharField(
        max_length=10,
        choices=PeyCodiStatus.choices,
        default=PeyCodiStatus.PENDING,
        verbose_name="estado de cuenta CoDi en pey",
    )
    pey_bank_account_id = models.CharField(
        max_length=64,
        blank=True,
        default="",
        verbose_name="id de cuenta en pey",
    )
    pey_codi_status_actualizado_en = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="última sincronización de estado pey",
    )
    cuenta_por_defecto = models.ForeignKey(
        "ambito.CuentaCobro", null=True, blank=True, on_delete=models.PROTECT,
        related_name="+",
    )
    secuencia_evento = models.BigIntegerField(default=0)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "comercio"
        verbose_name_plural = "comercios"
        ordering = ["nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["es_demo"], condition=models.Q(es_demo=True),
                name="comercio_un_solo_demo",
            ),
        ]

    def __str__(self) -> str:
        return self.nombre


class Membresia(models.Model):
    es_dueno = models.BooleanField(default=False)
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



class CuentaCobro(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    comercio = models.ForeignKey(
        Comercio, on_delete=models.PROTECT, related_name="cuentas"
    )
    clabe = models.CharField(max_length=18)
    pey_bank_account_id = models.CharField(max_length=64, blank=True, default="")
    codi_status_crudo = models.CharField(max_length=32, blank=True)
    codi_status = models.CharField(
        max_length=10,
        choices=[("pending", "Pendiente"), ("active", "Activa")],
        default="pending",
    )
    registro_estado = models.CharField(
        max_length=20,
        choices=[
            (v, v)
            for v in (
                "sin_registro",
                "registrando",
                "registrado",
                "incierto",
                "rechazado",
            )
        ],
        default="sin_registro",
    )
    version = models.PositiveIntegerField(default=1)
    sincronizada_en = models.DateTimeField(null=True, blank=True)
    ultimo_error = models.CharField(max_length=200, blank=True)
    anomalia = models.CharField(max_length=120, blank=True)
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["comercio", "creada_en"])]
        constraints = [
            models.UniqueConstraint(
                fields=["comercio", "clabe"], name="cuenta_clabe_unica_por_comercio"
            ),
            models.UniqueConstraint(
                fields=["pey_bank_account_id"],
                condition=~models.Q(pey_bank_account_id=""),
                name="cuenta_id_pey_unico",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    registro_estado__in=[
                        "sin_registro",
                        "registrando",
                        "registrado",
                        "incierto",
                        "rechazado",
                    ]
                ),
                name="cuenta_registro_valido",
            ),
            models.CheckConstraint(
                condition=models.Q(codi_status__in=["pending", "active"]),
                name="cuenta_status_valido",
            ),
            models.CheckConstraint(
                condition=~models.Q(codi_status="active")
                | (
                    ~models.Q(pey_bank_account_id="")
                    & models.Q(registro_estado="registrado")
                ),
                name="cuenta_active_exige_registro",
            ),
        ]


class OperacionCuenta(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cuenta = models.ForeignKey(
        CuentaCobro, on_delete=models.PROTECT, related_name="operaciones"
    )
    tipo = models.CharField(
        max_length=10, choices=[("registro", "Registro"), ("sync", "Sync")]
    )
    origen = models.CharField(
        max_length=10, choices=[("ui", "UI"), ("webhook", "Webhook")]
    )
    estado = models.CharField(
        max_length=12,
        choices=[
            (v, v)
            for v in (
                "pendiente",
                "en_curso",
                "aplicada",
                "incierta",
                "fallida",
                "descartada",
            )
        ],
    )
    clave = models.CharField(max_length=128, blank=True)
    hash_payload = models.CharField(max_length=64, blank=True)
    payload = models.JSONField(default=dict)
    version_reclamada = models.PositiveIntegerField(null=True, blank=True)
    sync_posterior = models.BooleanField(default=False)
    lease_token = models.UUIDField(null=True, blank=True)
    lease_hasta = models.DateTimeField(null=True, blank=True)
    request_id = models.CharField(max_length=64, blank=True)
    pey_bank_account_id_obtenido = models.CharField(max_length=64, blank=True)
    error = models.CharField(max_length=200, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    iniciado_en = models.DateTimeField(null=True, blank=True)
    terminado_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["cuenta", "clave"],
                condition=~models.Q(clave=""),
                name="operacion_cuenta_clave_unica",
            ),
            models.UniqueConstraint(
                fields=["cuenta"],
                condition=models.Q(
                    tipo="registro", estado__in=["pendiente", "en_curso", "incierta"]
                ),
                name="operacion_registro_vivo_unico",
            ),
            models.UniqueConstraint(
                fields=["cuenta"],
                condition=models.Q(tipo="sync", estado__in=["pendiente", "en_curso"]),
                name="operacion_sync_viva_unica",
            ),
        ]
