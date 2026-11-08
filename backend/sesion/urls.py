from django.urls import path

from sesion.views import EntrarSesionView, EstadoSesionView, SalirSesionView

urlpatterns = [
    path("entrar/", EntrarSesionView.as_view(), name="sesion-entrar"),
    path("estado/", EstadoSesionView.as_view(), name="sesion-estado"),
    path("salir/", SalirSesionView.as_view(), name="sesion-salir"),
]
