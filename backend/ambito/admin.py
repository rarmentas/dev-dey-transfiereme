from django.contrib import admin

from ambito.models import Comercio, Membresia


@admin.register(Comercio)
class ComercioAdmin(admin.ModelAdmin):
    list_display = ("nombre", "creado_en")
    search_fields = ("nombre",)


@admin.register(Membresia)
class MembresiaAdmin(admin.ModelAdmin):
    list_display = ("usuario", "comercio")
    list_filter = ("comercio",)
    search_fields = ("usuario__username", "comercio__nombre")
    autocomplete_fields = ("comercio",)
