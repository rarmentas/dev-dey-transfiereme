from django.urls import include, path, re_path

from config.frontend import aplicacion
from config.views import salud

urlpatterns = [
    path("api/salud/", salud, name="salud"),
    path("api/cuenta/", include("ambito.urls")),
    path("api/sesion/", include("sesion.urls")),
    path("api/movimientos/", include("movimientos.urls")),
    path("api/cobro/", include("movimientos.cobro_urls")),
    path("api/ventas/", include("ventas.urls")),
    path("api/pedidos/", include("pedidos.urls")),
    path("api/asistente-vivo/", include("asistente_vivo.urls")),
    path("api/webhooks/waha/", include("canales.urls")),
    path("api/webhooks/", include("webhooks.urls")),
    re_path(r"^(?P<ruta>.*)$", aplicacion, name="aplicacion"),
]
