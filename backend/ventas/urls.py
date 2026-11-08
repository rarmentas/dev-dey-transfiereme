from django.urls import path

from ventas.views import CrearVentaView
from ventas.views_estado import EstadoVentaView

urlpatterns = [
    path("", CrearVentaView.as_view(), name="ventas-crear"),
    path("<int:movimiento_id>/", EstadoVentaView.as_view(), name="ventas-estado"),
]
