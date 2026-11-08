from django.urls import include, path, re_path

from config.frontend import aplicacion
from config.views import salud

urlpatterns = [
    path("api/salud/", salud, name="salud"),
    path("api/cuenta/", include("ambito.urls")),
    path("api/sesion/", include("sesion.urls")),
    path("api/movimientos/", include("movimientos.urls")),
    path("api/webhooks/", include("webhooks.urls")),
    re_path(r"^(?P<ruta>.*)$", aplicacion, name="aplicacion"),
]
