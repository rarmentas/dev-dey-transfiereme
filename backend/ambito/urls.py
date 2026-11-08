from django.urls import path

from ambito.views import ActualizarComercioView, GuardarClabeView

urlpatterns = [
    path("clabe/", GuardarClabeView.as_view(), name="cuenta-clabe"),
    path("comercio/", ActualizarComercioView.as_view(), name="cuenta-comercio"),
]
