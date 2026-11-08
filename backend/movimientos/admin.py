from django.contrib import admin

from movimientos.models import Movimiento


@admin.register(Movimiento)
class MovimientoAdmin(admin.ModelAdmin):
    list_display = (
        "concepto_visible",
        "comercio",
        "monto",
        "canal",
        "estado",
        "origen",
        "creado_en",
    )
    list_filter = ("canal", "estado", "origen", "comercio")
    search_fields = ("concepto", "concepto_visible", "comercio__nombre")
    autocomplete_fields = ("comercio",)
    readonly_fields = ("creado_en", "actualizado_en")

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if obj is not None:
            fields.append("estado")
        return fields
