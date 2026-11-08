"""Registro y consulta de cuenta en pey. El transporte se inyecta; no hay red en tests."""

import logging
import re
from dataclasses import dataclass

from django.conf import settings

from ambito.clabe import clabe_es_valida
from pey.produccion import (
    TIMEOUT_S,
    _cuerpo_ilegible,
    _error_pey,
    _falla_http,
    _json,
    _objeto,
    _texto,
    transporte_urllib,
)
from pey.tipos import ErrorPey, ParametroInvalido

logger = logging.getLogger(__name__)

_ENTIDADES = frozenset({"BUSINESS", "PERSON"})
_ULID = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")


@dataclass(frozen=True)
class CuentaPey:
    id: str
    codi_status: str
    clabe: str = ""
    error_message: str = ""


def registrar_cuenta(
    *,
    alias: str,
    nombre: str,
    clabe: str,
    entidad: str,
    transporte=None,
) -> CuentaPey:
    """POST /bank-account. La CLABE inválida no sale del proceso."""
    _validar_registro(alias=alias, nombre=nombre, clabe=clabe, entidad=entidad)
    cuerpo = _json(
        [
            ("alias", alias),
            ("name", nombre),
            ("clabe", clabe),
            ("entity", entidad),
        ]
    )
    status, respuesta = _enviar("POST", "/bank-account", cuerpo, transporte)
    if status == 200:
        return _cuenta(_objeto(respuesta))
    if status == 404:
        raise _error_pey(respuesta)
    _falla_http(status, respuesta)


def consultar_cuenta(bank_account_id: str, *, transporte=None) -> CuentaPey:
    """GET /bank-account/{id}. No llama si el id no es un ULID."""
    if not isinstance(bank_account_id, str) or _ULID.fullmatch(bank_account_id) is None:
        raise ParametroInvalido("bank_account_id debe ser un ULID de 26 caracteres")
    identificador = bank_account_id
    status, respuesta = _enviar(
        "GET",
        f"/bank-account/{identificador}",
        b"",
        transporte,
    )
    if status == 200:
        return _cuenta(_objeto(respuesta))
    if status == 404:
        raise _error_pey(respuesta)
    _falla_http(status, respuesta)


def _validar_registro(*, alias: str, nombre: str, clabe: str, entidad: str) -> None:
    if not clabe_es_valida(clabe):
        raise ParametroInvalido("clabe inválida")
    if entidad not in _ENTIDADES:
        raise ParametroInvalido("entidad debe ser BUSINESS o PERSON")
    _texto_corto("alias", alias)
    _texto_corto("nombre", nombre)


def _texto_corto(campo: str, valor: object) -> None:
    if not isinstance(valor, str) or not 1 <= len(valor) <= 255:
        raise ParametroInvalido(f"{campo} debe tener de 1 a 255 caracteres")


def _enviar(metodo: str, ruta: str, cuerpo: bytes, transporte) -> tuple[int, bytes]:
    api_key = settings.PEY_API_KEY
    if not api_key:
        raise ErrorPey("CONFIGURACION", "Falta PEY_API_KEY.")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    url = f"{settings.PEY_BASE_URL.rstrip('/')}{ruta}"
    usado = transporte if transporte is not None else transporte_urllib
    try:
        return usado(metodo, url, headers, cuerpo, TIMEOUT_S)
    except Exception as exc:
        logger.warning("pey no disponible (%s)", exc.__class__.__name__)
        raise ErrorPey(
            "NO_DISPONIBLE",
            "pey no respondió",
            puede_haberse_creado=True,
        ) from exc


def _cuenta(data: dict) -> CuentaPey:
    mensaje = data.get("errorMessage")
    if mensaje is None:
        mensaje = ""
    if not isinstance(mensaje, str):
        raise _cuerpo_ilegible()
    clabe = data.get("clabe")
    if clabe is None:
        clabe = ""
    if not isinstance(clabe, str):
        raise _cuerpo_ilegible()
    return CuentaPey(
        id=_texto(data, "id"),
        codi_status=_texto(data, "codiStatus"),
        clabe=clabe,
        error_message=mensaje,
    )
