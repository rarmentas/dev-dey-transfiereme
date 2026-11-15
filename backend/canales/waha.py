"""Transporte HTTP privado de WAHA."""

import json
from urllib import error, request
from urllib.parse import quote

from django.conf import settings


class ErrorEnvio(Exception):
    def __init__(self, definitivo=False):
        self.definitivo = definitivo


class SinRedireccion(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class AdaptadorWaha:
    def establecer_presencia(self, sesion_id: str, chat_id: str, presencia: str) -> None:
        cuerpo = json.dumps({"chatId": chat_id, "presence": presencia}).encode()
        req = request.Request(
            settings.WAHA_BASE_URL.rstrip("/") + f"/api/{quote(sesion_id, safe='')}/presence",
            data=cuerpo,
            headers={"Content-Type": "application/json", "X-Api-Key": settings.WAHA_API_KEY},
            method="POST",
        )
        with request.build_opener(SinRedireccion()).open(req, timeout=5):
            pass

    def iniciar_escritura(self, sesion_id: str, chat_id: str) -> None:
        self.establecer_presencia(sesion_id, chat_id, "typing")

    def detener_escritura(self, sesion_id: str, chat_id: str) -> None:
        self.establecer_presencia(sesion_id, chat_id, "paused")

    def enviar_texto(self, sesion_id: str, chat_id: str, texto: str) -> str:
        cuerpo = json.dumps(
            {"session": sesion_id, "chatId": chat_id, "text": texto}
        ).encode()
        req = request.Request(
            settings.WAHA_BASE_URL.rstrip("/") + "/api/sendText",
            data=cuerpo,
            headers={
                "Content-Type": "application/json",
                "X-Api-Key": settings.WAHA_API_KEY,
            },
            method="POST",
        )
        try:
            with request.build_opener(SinRedireccion()).open(
                req, timeout=10
            ) as respuesta:
                datos = json.load(respuesta)
            identidad = datos.get("id") if isinstance(datos, dict) else None
            if isinstance(identidad, dict):
                identidad = identidad.get("_serialized")
            if not identidad and isinstance(datos, dict):
                clave = datos.get("key")
                identidad = clave.get("id") if isinstance(clave, dict) else None
            if not isinstance(identidad, str) or not identidad or len(identidad) > 200:
                raise ErrorEnvio()
            return identidad
        except error.HTTPError as exc:
            raise ErrorEnvio(400 <= exc.code < 500) from exc
        except (error.URLError, TimeoutError, OSError, ValueError) as exc:
            raise ErrorEnvio() from exc
