from django.urls import path

from pedidos.views import (
    CotizacionesPedidoView,
    DetallePedidoView,
    ListaPedidosView,
    RenglonesPedidoView,
)

urlpatterns = [
    path("", ListaPedidosView.as_view(), name="pedidos-lista"),
    path("<str:pedido_id>/", DetallePedidoView.as_view(), name="pedidos-detalle"),
    path(
        "<str:pedido_id>/renglones/",
        RenglonesPedidoView.as_view(),
        name="pedidos-renglones",
    ),
    path(
        "<str:pedido_id>/cotizaciones/",
        CotizacionesPedidoView.as_view(),
        name="pedidos-cotizaciones",
    ),
]
