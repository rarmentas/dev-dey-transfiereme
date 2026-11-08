"""Serializers de lectura de movimientos (sin escritura en esta historia)."""

from rest_framework import serializers

from movimientos.models import Movimiento


class MovimientoLecturaSerializer(serializers.ModelSerializer):
    monto = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        coerce_to_string=True,
    )

    class Meta:
        model = Movimiento
        fields = (
            "id",
            "monto",
            "concepto_visible",
            "canal",
            "estado",
            "origen",
            "creado_en",
            "pagado_en",
        )
        read_only_fields = fields
