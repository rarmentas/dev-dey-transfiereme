from django.urls import path

from ambito.views_cuenta_pey import (
    EstadoCuentaPeyView,
    RegistrarCuentaPeyView,
    SincronizarCuentaPeyView,
)

urlpatterns = [
    path("estado/", EstadoCuentaPeyView.as_view(), name="cuenta-pey-estado"),
    path("registro/", RegistrarCuentaPeyView.as_view(), name="cuenta-pey-registro"),
    path("sincronizar/", SincronizarCuentaPeyView.as_view(), name="cuenta-pey-sincronizar"),
]
