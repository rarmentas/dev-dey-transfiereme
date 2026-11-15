"""Descarga acotada desde el origen de WAHA."""

import time
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from django.conf import settings


class ErrorAudio(Exception):
    def __init__(self, motivo):
        self.motivo = motivo
        super().__init__(motivo)


class SinRedireccion(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def origen_permitido(url: str) -> bool:
    try:
        destino = urlsplit(url)
        base = urlsplit(settings.WAHA_BASE_URL)
        ruta = unquote(destino.path)
        return bool(
            destino.scheme in ("http", "https")
            and (destino.scheme, destino.hostname, destino.port)
            == (base.scheme, base.hostname, base.port)
            and destino.hostname
            and "@" not in destino.netloc
            and not destino.username
            and not destino.password
            and not destino.query
            and not destino.fragment
            and "%2e" not in destino.path.lower()
            and ruta.startswith("/api/files/")
            and ".." not in ruta
            and "\\" not in ruta
            and not any(ord(caracter) < 32 for caracter in ruta)
            and "%" not in ruta
        )
    except (ValueError, TypeError):
        return False


def descargar_acotado(url: str, destino, timeout: float, opener=None) -> None:
    if not origen_permitido(url):
        raise ErrorAudio("fuera_de_origen")
    request = Request(url, headers={"X-Api-Key": settings.WAHA_API_KEY})
    limite = time.monotonic() + timeout
    try:
        with (opener or build_opener(SinRedireccion())).open(
            request, timeout=timeout
        ) as respuesta:
            if 300 <= respuesta.status < 400:
                raise ErrorAudio("redireccion")
            largo = respuesta.headers.get("Content-Length")
            if largo and int(largo) > settings.WHATSAPP_AUDIO_MAX_BYTES:
                raise ErrorAudio("demasiado_grande")
            total = 0
            with open(destino, "wb") as archivo:
                while True:
                    if time.monotonic() >= limite:
                        raise ErrorAudio("descarga")
                    bloque = respuesta.read(65536)
                    if not bloque:
                        break
                    total += len(bloque)
                    if total > settings.WHATSAPP_AUDIO_MAX_BYTES:
                        raise ErrorAudio("demasiado_grande")
                    archivo.write(bloque)
            if not total:
                raise ErrorAudio("vacio")
    except HTTPError as exc:
        raise ErrorAudio(
            "redireccion" if 300 <= exc.code < 400 else "descarga"
        ) from exc
    except (URLError, OSError, ValueError, TimeoutError) as exc:
        raise ErrorAudio("descarga") from exc
