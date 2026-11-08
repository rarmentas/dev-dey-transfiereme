from django.urls import include, path

from config.views import salud

urlpatterns = [
    path("api/salud/", salud, name="salud"),
    path("api/cuenta/", include("ambito.urls")),
    path("api/sesion/", include("sesion.urls")),
    path("api/movimientos/", include("movimientos.urls")),
    path("api/webhooks/", include("webhooks.urls")),
]
