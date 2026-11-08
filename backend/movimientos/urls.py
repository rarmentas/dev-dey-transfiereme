from django.urls import path

from movimientos.views import DetalleMovimientoView, ListadoMovimientosView

urlpatterns = [
    path("", ListadoMovimientosView.as_view(), name="movimientos-listado"),
    path("<int:pk>/", DetalleMovimientoView.as_view(), name="movimientos-detalle"),
]
