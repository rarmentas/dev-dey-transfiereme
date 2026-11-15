from django.contrib import admin

from ambito.models import Comercio, CuentaCobro, Membresia


@admin.register(Comercio)
class ComercioAdmin(admin.ModelAdmin):
    list_display = ("nombre", "semilla_active_dev", "es_demo", "creado_en")
    readonly_fields = ("es_demo",)
    exclude = (
        "clabe", "pey_codi_status", "pey_bank_account_id",
        "pey_codi_status_actualizado_en", "cuenta_por_defecto",
    )
    search_fields = ("nombre",)


@admin.register(Membresia)
class MembresiaAdmin(admin.ModelAdmin):
    list_display = ("usuario", "comercio")
    list_filter = ("comercio",)
    search_fields = ("usuario__username", "comercio__nombre")
    autocomplete_fields = ("comercio",)


@admin.register(CuentaCobro)
class CuentaCobroAdmin(admin.ModelAdmin):
    list_display = ("id", "comercio", "registro_estado", "codi_status")
    readonly_fields = tuple(field.name for field in CuentaCobro._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
