import json
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

PREFIJO_WEBHOOKS_API = "/api/webhooks/"
PREFIJO_SESION_ENTRAR = "/api/sesion/entrar/"
PREFIJO_SESION_ESTADO = "/api/sesion/estado/"
RUTA_SALUD = "/api/salud/"

# alta: añadir prefijos aquí cuando exista registro público
RUTAS_ALTA_EXENTAS: tuple[str, ...] = ()

_MENSAJE_SIN_SESION = "Debe iniciar sesión."


def ruta_exenta(path: str, method: str) -> bool:
    if not path.startswith("/api/"):
        return True
    for prefijo in RUTAS_ALTA_EXENTAS:
        if path.startswith(prefijo):
            return True
    if path.startswith(PREFIJO_WEBHOOKS_API):
        return True
    if method == "GET" and path.rstrip("/") + "/" == RUTA_SALUD:
        return True
    if path.startswith(PREFIJO_SESION_ESTADO):
        return True
    if method == "POST" and path.startswith(PREFIJO_SESION_ENTRAR):
        return True
    return False


def _respuesta_sin_sesion() -> HttpResponse:
    return HttpResponse(
        json.dumps({"detail": _MENSAJE_SIN_SESION}, ensure_ascii=False),
        status=403,
        content_type="application/json",
    )


class CierraApiSinSesionMiddleware:
    """Responde 403 en /api/ sin usuario autenticado, salvo rutas exentas (R7)."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if (
            request.path.startswith("/api/")
            and not request.user.is_authenticated
            and not ruta_exenta(request.path, request.method)
        ):
            return _respuesta_sin_sesion()
        return self.get_response(request)
