from django.contrib import admin

from movimientos.models import Cobro, Movimiento


@admin.register(Cobro)
class CobroAdmin(admin.ModelAdmin):
    list_display = (
        "concepto",
        "comercio",
        "monto",
        "canal",
        "pey_qr_id",
        "pey_transaction_id",
        "vence_en",
        "creado_en",
    )
    list_filter = ("canal", "comercio")
    search_fields = ("concepto", "pey_qr_id", "pey_transaction_id", "comercio__nombre")
    autocomplete_fields = ("comercio",)
    readonly_fields = ("creado_en",)


@admin.register(Movimiento)
class MovimientoAdmin(admin.ModelAdmin):
    list_display = (
        "concepto_visible",
        "comercio",
        "cobro",
        "monto",
        "canal",
        "estado",
        "origen",
        "creado_en",
    )
    list_filter = ("canal", "estado", "origen", "comercio")
    search_fields = (
        "concepto",
        "concepto_visible",
        "comercio__nombre",
        "pey_transaction_id",
    )
    autocomplete_fields = ("comercio", "cobro")
    readonly_fields = ("creado_en", "actualizado_en")

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if obj is not None:
            fields.append("estado")
        return fields
