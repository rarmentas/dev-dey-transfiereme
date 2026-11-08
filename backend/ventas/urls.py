from django.urls import path

from ventas.views import CrearVentaView

urlpatterns = [
    path("", CrearVentaView.as_view(), name="ventas-crear"),
]
