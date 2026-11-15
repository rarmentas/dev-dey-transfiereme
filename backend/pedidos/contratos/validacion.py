"""Validación y huella compartidas por las implementaciones del puerto."""

import hashlib
import json
from decimal import Decimal, InvalidOperation
from uuid import UUID

from .v1 import (
    CANTIDAD_MAXIMA,
    CONTRATO_VERSION,
    MAX_COMMAND_KEY,
    MAX_MENSAJE,
    MAX_RENGLONES,
    CanalCobro,
    CodigoError,
    RenglonSolicitadoV1,
    serializar,
)


class ErrorContrato(Exception):
    def __init__(self, codigo: CodigoError, detalle: str):
        self.codigo = codigo
        self.detalle = detalle
        super().__init__(detalle)


def _invalido(detalle: str) -> None:
    raise ErrorContrato(CodigoError.PAYLOAD_INVALIDO, detalle)


_COMUN = {"contrato_version"}
_ESQUEMAS = {
    "registrar_solicitud": (
        _COMUN
        | {
            "command_key",
            "mensaje_id",
            "message_key",
            "secuencia_conversacion",
            "renglones",
        },
        set(),
    ),
    "corregir_borrador": (
        _COMUN
        | {
            "command_key",
            "pedido_id",
            "expected_version",
            "mensaje_id",
            "message_key",
            "secuencia_conversacion",
            "renglones",
        },
        set(),
    ),
    "consultar_pedido": (_COMUN | {"pedido_id"}, set()),
    "aceptar_cotizacion": (
        _COMUN
        | {
            "command_key",
            "pedido_id",
            "expected_version",
            "cotizacion_id",
            "cotizacion_revision",
            "importe_efectivo_mostrado_centavos",
            "politica_cobro_version",
            "mensaje_consentimiento_id",
            "token_resumen",
        },
        set(),
    ),
    "solicitar_cobro": (
        _COMUN
        | {"command_key", "pedido_id", "expected_version", "aceptacion_id", "canal"},
        {"telefono_bancario_confirmado"},
    ),
    "consultar_eventos": (_COMUN | {"cursor"}, {"limite"}),
}


def validar_cantidad(valor: object) -> Decimal:
    if not isinstance(valor, (Decimal, str)):
        _invalido("La cantidad debe ser Decimal o texto decimal.")
    try:
        cantidad = Decimal(valor)
    except (InvalidOperation, ValueError):
        _invalido("Cantidad inválida.")
    if (
        not cantidad.is_finite()
        or cantidad.as_tuple().exponent < -3
        or not Decimal(0) < cantidad <= CANTIDAD_MAXIMA
    ):
        _invalido("Cantidad fuera de rango o escala.")
    return cantidad


def validar_comando(operacion: str, datos: dict) -> None:
    if not isinstance(datos, dict) or operacion not in _ESQUEMAS:
        _invalido("Operación o cuerpo inválido.")
    if datos.get("contrato_version") != CONTRATO_VERSION:
        raise ErrorContrato(
            CodigoError.VERSION_CONTRATO_NO_SOPORTADA,
            "Versión de contrato no soportada.",
        )
    requeridos, opcionales = _ESQUEMAS[operacion]
    if requeridos - datos.keys() or datos.keys() - requeridos - opcionales:
        _invalido("Campos faltantes o desconocidos.")
    for clave in (
        "command_key",
        "message_key",
        "politica_cobro_version",
        "token_resumen",
    ):
        if clave in datos:
            valor = datos[clave]
            limite = MAX_COMMAND_KEY if clave == "command_key" else MAX_MENSAJE
            if not isinstance(valor, str) or not valor.strip() or len(valor) > limite:
                _invalido(f"{clave} inválido.")
    for clave in (
        "pedido_id",
        "mensaje_id",
        "cotizacion_id",
        "aceptacion_id",
        "mensaje_consentimiento_id",
    ):
        if clave in datos:
            try:
                if not isinstance(datos[clave], str):
                    raise ValueError
                UUID(datos[clave])
            except (ValueError, TypeError, AttributeError):
                _invalido(f"{clave} inválido.")
    for clave in (
        "expected_version",
        "secuencia_conversacion",
        "cotizacion_revision",
        "importe_efectivo_mostrado_centavos",
        "limite",
    ):
        if clave in datos and (type(datos[clave]) is not int or datos[clave] <= 0):
            _invalido(f"{clave} inválido.")
    if datos.get("limite", 1) > 100:
        _invalido("Límite inválido.")
    if (
        "cursor" in datos
        and datos["cursor"] is not None
        and not isinstance(datos["cursor"], str)
    ):
        _invalido("Cursor inválido.")
    if "canal" in datos and datos["canal"] not in [c.value for c in CanalCobro]:
        _invalido("Canal inválido.")
    if "telefono_bancario_confirmado" in datos:
        telefono = datos["telefono_bancario_confirmado"]
        if telefono is not None and (
            not isinstance(telefono, str)
            or len(telefono) != 10
            or not telefono.isascii()
            or not telefono.isdigit()
        ):
            _invalido("Teléfono inválido.")
    if datos.get("canal") == "notificacion" and not datos.get(
        "telefono_bancario_confirmado"
    ):
        _invalido("Falta teléfono confirmado.")
    if "renglones" in datos:
        renglones = datos["renglones"]
        if (
            not isinstance(renglones, (list, tuple))
            or not 1 <= len(renglones) <= MAX_RENGLONES
        ):
            _invalido("Cantidad de renglones inválida.")
        ids = set()
        for renglon in renglones:
            if isinstance(renglon, RenglonSolicitadoV1):
                renglon = renglon.a_dict()
            if (
                not isinstance(renglon, dict)
                or set(renglon)
                - {
                    "renglon_id",
                    "texto_solicitado",
                    "cantidad_solicitada",
                    "unidad_solicitada",
                }
                or not {"renglon_id", "texto_solicitado"} <= renglon.keys()
            ):
                _invalido("Renglón inválido.")
            try:
                if not isinstance(renglon["renglon_id"], str):
                    raise ValueError
                identidad = UUID(renglon["renglon_id"])
            except (ValueError, TypeError, AttributeError):
                _invalido("ID de renglón inválido.")
            if identidad in ids:
                _invalido("ID de renglón repetido.")
            ids.add(identidad)
            texto = renglon["texto_solicitado"]
            if not isinstance(texto, str) or not texto.strip() or len(texto) > 500:
                _invalido("Texto solicitado inválido.")
            cantidad = renglon.get("cantidad_solicitada")
            if cantidad is not None:
                validar_cantidad(cantidad)
            unidad = renglon.get("unidad_solicitada")
            if unidad is not None and (not isinstance(unidad, str) or len(unidad) > 30):
                _invalido("Unidad inválida.")


def hash_canonico(operacion: str, datos: dict, ctx: object) -> str:
    cuerpo = {
        "operacion": operacion,
        "datos": {k: v for k, v in datos.items() if k != "command_key"},
        "ctx": ctx,
    }
    texto = json.dumps(
        serializar(cuerpo),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()
