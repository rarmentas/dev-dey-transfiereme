"""Sirve el build web de Flutter que deja el deploy en FRONTEND_DIST.

La API sigue registrada aparte. Un archivo que existe en el build se entrega
tal cual. Una ruta de la app (/, /entrar, /inicio) entrega index.html para
que GoRouter la resuelva en el navegador. Si piden un archivo que no está,
la respuesta es 404: el navegador no debe recibir HTML donde espera JS.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404, HttpRequest, HttpResponseRedirect

mimetypes.add_type("application/javascript", ".js", strict=True)
mimetypes.add_type("application/wasm", ".wasm", strict=True)
mimetypes.add_type("application/json", ".json", strict=True)
mimetypes.add_type("font/woff2", ".woff2", strict=True)
mimetypes.add_type("font/ttf", ".ttf", strict=True)

_PREFIJOS_AJENOS = ("api/", "static/")


def aplicacion(request: HttpRequest, ruta: str = "") -> FileResponse | HttpResponseRedirect:
    if request.method not in ("GET", "HEAD"):
        raise Http404
    if ruta.startswith(_PREFIJOS_AJENOS) or ruta in ("api", "static"):
        raise Http404

    dist = Path(settings.FRONTEND_DIST)
    indice = _indice(dist)

    if ruta.endswith("/"):
        destino = "/" + ruta.strip("/")
        consulta = request.META.get("QUERY_STRING", "")
        if consulta:
            destino = f"{destino}?{consulta}"
        return HttpResponseRedirect(destino)

    relativa = ruta.strip("/")
    if not relativa:
        return _archivo(indice, html=True)

    archivo = _archivo_pedido(dist, relativa)
    if archivo is None:
        return _archivo(indice, html=True)
    return _archivo(archivo)


def _indice(dist: Path) -> Path:
    indice = (dist / "index.html").resolve()
    if not _esta_dentro(dist, indice) or not indice.is_file():
        raise Http404
    return indice


def _archivo_pedido(dist: Path, relativa: str) -> Path | None:
    """Archivo real dentro del build, o None si la ruta es de GoRouter.

    Una ruta que sale del directorio, o un archivo que no está, responde 404.
    """
    raiz = dist.resolve()
    candidato = (raiz / relativa).resolve()
    if not _esta_dentro(raiz, candidato):
        raise Http404
    if candidato.is_file():
        return candidato
    if _parece_archivo(relativa):
        raise Http404
    return None


def _esta_dentro(raiz: Path, candidato: Path) -> bool:
    try:
        candidato.resolve().relative_to(raiz.resolve())
    except ValueError:
        return False
    return True


def _parece_archivo(relativa: str) -> bool:
    nombre = relativa.rsplit("/", 1)[-1]
    return "." in nombre


def _archivo(archivo: Path, html: bool = False) -> FileResponse:
    if html:
        tipo = "text/html; charset=utf-8"
    else:
        tipo = mimetypes.guess_type(archivo.name)[0] or "application/octet-stream"
    respuesta = FileResponse(archivo.open("rb"), content_type=tipo, as_attachment=False)
    respuesta["Cache-Control"] = "no-cache"
    return respuesta
