"""Adaptador de producción. El transporte se inyecta; los tests no salen a la red."""

import json
import logging
from collections.abc import Callable
from decimal import Decimal
from typing import NoReturn
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from django.conf import settings

from ambito.cuenta import cuenta_esta_active
from ambito.models import Comercio

from pey.tipos import ErrorPey, NotificacionCreada, QrCreado
from pey.validacion import NotificacionValidada, QrValidado, validar_notificacion, validar_qr

logger = logging.getLogger(__name__)

TIMEOUT_S = 10

Transporte = Callable[
    [str, str, dict[str, str], bytes, float],
    tuple[int, bytes],
]


class _SinRedireccion(HTTPRedirectHandler):
    """Un 3xx no se sigue: el Bearer no debe salir hacia otro host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def transporte_urllib(
    metodo: str,
    url: str,
    headers: dict[str, str],
    cuerpo_bytes: bytes,
    timeout: float,
) -> tuple[int, bytes]:
    opener = build_opener(_SinRedireccion)
    peticion = Request(url, data=cuerpo_bytes, headers=headers, method=metodo)
    try:
        with opener.open(peticion, timeout=timeout) as respuesta:
            return int(respuesta.status), respuesta.read()
    except HTTPError as exc:
        with exc:
            return exc.code, exc.read()


class AdaptadorProduccion:
    def __init__(self, transporte: Transporte | None = None) -> None:
        self._transporte = transporte if transporte is not None else transporte_urllib

    def crear_qr(
        self,
        *,
        monto: Decimal,
        concepto: str = "",
        expiracion_s: int = 0,
        num_ref: str = "0",
        bank_account_id: str = "",
    ) -> QrCreado:
        datos = validar_qr(
            monto=monto,
            concepto=concepto,
            expiracion_s=expiracion_s,
            num_ref=num_ref,
            bank_account_id=bank_account_id,
        )
        status, cuerpo = self._post("/codi/qr", _cuerpo_qr(datos))
        if status == 201:
            data = _objeto(cuerpo)
            return QrCreado(id=_texto(data, "id"), qr_string=_texto(data, "qrString"))
        _falla_http(status, cuerpo)

    def crear_notificacion(
        self,
        *,
        monto: Decimal,
        telefono: str,
        concepto: str = "",
        expiracion_s: int = 360,
        num_ref: str = "0",
        bank_account_id: str = "",
    ) -> NotificacionCreada:
        datos = validar_notificacion(
            monto=monto,
            telefono=telefono,
            concepto=concepto,
            expiracion_s=expiracion_s,
            num_ref=num_ref,
            bank_account_id=bank_account_id,
        )
        status, cuerpo = self._post("/codi/pn", _cuerpo_pn(datos))
        if status == 200:
            data = _objeto(cuerpo)
            return NotificacionCreada(
                transaction_id=_texto(data, "transactionId"),
                codi_id=_texto(data, "codiId"),
            )
        _falla_http(status, cuerpo)

    def cuenta_active(self, comercio: Comercio) -> bool:
        # El codiStatus real lo consultan 5.2 y 5.4; este gate no lee la semilla.
        return cuenta_esta_active(comercio)

    def _post(self, ruta: str, cuerpo: bytes) -> tuple[int, bytes]:
        api_key = settings.PEY_API_KEY
        if not api_key:
            raise ErrorPey("CONFIGURACION", "Falta PEY_API_KEY.")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        url = f"{settings.PEY_BASE_URL.rstrip('/')}{ruta}"
        try:
            return self._transporte("POST", url, headers, cuerpo, TIMEOUT_S)
        except Exception as exc:
            logger.warning("pey no disponible (%s)", exc.__class__.__name__)
            raise ErrorPey(
                "NO_DISPONIBLE",
                "pey no respondió",
                puede_haberse_creado=True,
            ) from exc


def _cuerpo_qr(datos: QrValidado) -> bytes:
    campos: list[tuple[str, object]] = [
        ("amount", datos.monto),
        ("concept", datos.concepto),
        ("expiration", datos.expiracion_s),
        ("numRef", datos.num_ref),
    ]
    if datos.bank_account_id:
        campos.append(("bankAccountId", datos.bank_account_id))
    return _json(campos)


def _cuerpo_pn(datos: NotificacionValidada) -> bytes:
    campos: list[tuple[str, object]] = [
        ("amount", datos.monto),
        ("phoneNumber", datos.telefono),
        ("concept", datos.concepto),
        ("expiration", datos.expiracion_s),
        ("numRef", datos.num_ref),
    ]
    if datos.bank_account_id:
        campos.append(("bankAccountId", datos.bank_account_id))
    return _json(campos)


def _json(campos: list[tuple[str, object]]) -> bytes:
    pares = [f'"{clave}": {_fragmento(valor)}' for clave, valor in campos]
    return ("{" + ", ".join(pares) + "}").encode("utf-8")


def _fragmento(valor: object) -> str:
    if isinstance(valor, Decimal):
        return format(valor, "f")
    return json.dumps(valor, ensure_ascii=False)


def _objeto(cuerpo: bytes) -> dict:
    try:
        data = json.loads(cuerpo)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        raise _cuerpo_ilegible() from None
    if not isinstance(data, dict):
        raise _cuerpo_ilegible()
    return data


def _texto(data: dict, campo: str) -> str:
    valor = data.get(campo)
    if not isinstance(valor, str) or valor == "":
        raise _cuerpo_ilegible()
    return valor


def _cuerpo_ilegible() -> ErrorPey:
    return ErrorPey(
        "RESPUESTA_INVALIDA",
        "pey respondió un cuerpo ilegible",
        puede_haberse_creado=True,
    )


def _falla_http(status: int, cuerpo: bytes) -> NoReturn:
    if status == 400:
        raise _error_pey(cuerpo)
    if 500 <= status <= 599:
        request_id = _request_id(cuerpo)
        _loguear("NO_DISPONIBLE", request_id)
        raise ErrorPey(
            "NO_DISPONIBLE",
            "pey no está disponible",
            request_id,
            puede_haberse_creado=True,
        )
    request_id = _request_id(cuerpo)
    _loguear("RESPUESTA_INVALIDA", request_id)
    raise ErrorPey(
        "RESPUESTA_INVALIDA",
        "pey respondió un estado inesperado",
        request_id,
        puede_haberse_creado=True,
    )


def _error_pey(cuerpo: bytes) -> ErrorPey:
    data = _objeto_o_invalido(cuerpo)
    error = data.get("error") if data is not None else None
    if not isinstance(error, dict):
        raise ErrorPey("RESPUESTA_INVALIDA", "pey respondió un error ilegible")
    tipo = error.get("type")
    mensaje = error.get("message")
    request_id = error.get("requestId")
    if not isinstance(tipo, str) or tipo == "" or not isinstance(mensaje, str):
        raise ErrorPey("RESPUESTA_INVALIDA", "pey respondió un error ilegible")
    if request_id is not None and not isinstance(request_id, str):
        raise ErrorPey("RESPUESTA_INVALIDA", "pey respondió un error ilegible")
    _loguear(tipo, request_id)
    return ErrorPey(tipo, mensaje, request_id)


def _objeto_o_invalido(cuerpo: bytes) -> dict | None:
    try:
        data = json.loads(cuerpo)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def _request_id(cuerpo: bytes) -> str | None:
    data = _objeto_o_invalido(cuerpo)
    if data is None:
        return None
    error = data.get("error")
    if not isinstance(error, dict):
        return None
    request_id = error.get("requestId")
    if isinstance(request_id, str):
        return request_id
    return None


def _loguear(tipo: str, request_id: str | None) -> None:
    logger.warning("error de pey tipo=%s requestId=%s", tipo, request_id)
