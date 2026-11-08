from django.urls import include, path

from ambito.views import ActualizarComercioView, GuardarClabeView

urlpatterns = [
    path("clabe/", GuardarClabeView.as_view(), name="cuenta-clabe"),
    path("comercio/", ActualizarComercioView.as_view(), name="cuenta-comercio"),
    path("pey/", include("ambito.urls_cuenta_pey")),
]
