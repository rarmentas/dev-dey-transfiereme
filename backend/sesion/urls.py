from django.urls import path

from sesion.views import EntrarSesionView, EstadoSesionView, SalirSesionView
from sesion.views_alta_olvido import (
    AltaConfirmarView,
    AltaSolicitarView,
    OlvidoRestablecerView,
    OlvidoSolicitarView,
)

urlpatterns = [
    path("entrar/", EntrarSesionView.as_view(), name="sesion-entrar"),
    path("estado/", EstadoSesionView.as_view(), name="sesion-estado"),
    path("salir/", SalirSesionView.as_view(), name="sesion-salir"),
    path("alta/solicitar/", AltaSolicitarView.as_view(), name="sesion-alta-solicitar"),
    path("alta/confirmar/", AltaConfirmarView.as_view(), name="sesion-alta-confirmar"),
    path(
        "olvido/solicitar/",
        OlvidoSolicitarView.as_view(),
        name="sesion-olvido-solicitar",
    ),
    path(
        "olvido/restablecer/",
        OlvidoRestablecerView.as_view(),
        name="sesion-olvido-restablecer",
    ),
]
