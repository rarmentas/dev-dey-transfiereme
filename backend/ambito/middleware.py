from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from ambito.models import Membresia


class AmbitoComercioMiddleware:
    """Fija request.comercio según la membresía del usuario autenticado (C5)."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request.comercio = None
        if request.user.is_authenticated:
            membresia = (
                Membresia.objects.select_related("comercio")
                .filter(usuario_id=request.user.pk)
                .first()
            )
            if membresia is not None:
                request.comercio = membresia.comercio
        return self.get_response(request)
