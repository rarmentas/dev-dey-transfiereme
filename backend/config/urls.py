from django.urls import include, path

from config.views import salud

urlpatterns = [
    path("api/salud/", salud, name="salud"),
    path("api/sesion/", include("sesion.urls")),
]
