from django.urls import path

from pedidos.views import (
    AgenteConfiguracionView,
    CatalogoView,
    ProductoView,
    CotizacionesPedidoView,
    CobroPedidoView,
    CancelarPedidoView,
    DetallePedidoView,
    EntregadoPedidoView,
    ListoPedidoView,
    ListaPedidosView,
    RenglonesPedidoView,
)

urlpatterns = [
    path("catalogo/", CatalogoView.as_view(), name="pedidos-catalogo"),
    path("catalogo/<int:producto_id>/", ProductoView.as_view(), name="pedidos-producto"),
    path("agente/", AgenteConfiguracionView.as_view(), name="pedidos-agente"),
    path("", ListaPedidosView.as_view(), name="pedidos-lista"),
    path("<str:pedido_id>/cobro/", CobroPedidoView.as_view(), name="pedidos-cobro"),
    path(
        "<str:pedido_id>/cancelar/",
        CancelarPedidoView.as_view(),
        name="pedidos-cancelar",
    ),
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
