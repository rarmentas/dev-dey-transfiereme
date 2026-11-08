from django.urls import path

from movimientos.views import (
    DetalleMovimientoView,
    ListadoMovimientosView,
    TableroView,
)

urlpatterns = [
    path("", ListadoMovimientosView.as_view(), name="movimientos-listado"),
    path("tablero/", TableroView.as_view(), name="movimientos-tablero"),
    path("<int:pk>/", DetalleMovimientoView.as_view(), name="movimientos-detalle"),
]
