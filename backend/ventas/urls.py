from django.urls import path

from ventas.views import CrearNotificacionView, CrearVentaView

urlpatterns = [
    path("", CrearVentaView.as_view(), name="ventas-crear"),
    path(
        "notificacion/",
        CrearNotificacionView.as_view(),
        name="ventas-notificacion",
    ),
]
