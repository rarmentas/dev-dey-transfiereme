from django.urls import path

from ventas.views import CrearNotificacionView, CrearVentaView
from ventas.views_estado import EstadoVentaView

urlpatterns = [
    path("", CrearVentaView.as_view(), name="ventas-crear"),
    path(
        "notificacion/",
        CrearNotificacionView.as_view(),
        name="ventas-notificacion",
    ),
    path("<int:movimiento_id>/", EstadoVentaView.as_view(), name="ventas-estado"),
]
