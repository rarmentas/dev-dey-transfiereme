from django.contrib import admin

from webhooks.models import AvisoRecibido


@admin.register(AvisoRecibido)
class AvisoRecibidoAdmin(admin.ModelAdmin):
    list_display = (
        "webhook_id",
        "tipo",
        "transaction_id",
        "resultado",
        "movimiento",
        "recibido_en",
    )
    list_filter = ("resultado", "tipo")
    search_fields = ("webhook_id", "transaction_id", "tipo")
    readonly_fields = (
        "webhook_id",
        "tipo",
        "transaction_id",
        "resultado",
        "movimiento",
        "recibido_en",
    )

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False
