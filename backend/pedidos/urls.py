from django.urls import path

from pedidos.views import (
    CotizacionesPedidoView,
    CobroPedidoView,
    DetallePedidoView,
    EntregadoPedidoView,
    ListoPedidoView,
    ListaPedidosView,
    RenglonesPedidoView,
)

urlpatterns = [
    path("", ListaPedidosView.as_view(), name="pedidos-lista"),
    path("<str:pedido_id>/cobro/", CobroPedidoView.as_view(), name="pedidos-cobro"),
    path("<str:pedido_id>/listo/", ListoPedidoView.as_view(), name="pedidos-listo"),
    path(
        "<str:pedido_id>/entregado/",
        EntregadoPedidoView.as_view(),
        name="pedidos-entregado",
    ),
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
