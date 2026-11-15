"""Puerto HTTP del aviso de pey. No llama a pey."""

import hashlib
import json
import re
import logging
from dataclasses import dataclass
from datetime import datetime, timezone as zona_utc
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ImproperlyConfigured
from django.db import IntegrityError, transaction
from django.http import HttpRequest, HttpResponseNotFound, JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from ambito.models import CuentaCobro
from ambito.operaciones_cuenta import encolar_sync
from movimientos.correlacion import TIPO_PN, TIPO_QR, AvisoPago
from movimientos.models import Movimiento
from pey.seleccion import modo_adaptador
from webhooks.models import AvisoRecibido
from webhooks.verificacion import FirmaInvalida, verificar_firma

logger = logging.getLogger(__name__)

_LARGO_WEBHOOK_ID = 128
_LARGO_TIPO = 128
_LARGO_TRANSACTION_ID = 64
_MONTO_MAXIMO = Decimal(10) ** 10
TIPO_CUENTA = "bank.account.updated"
_TIPOS_CONOCIDOS = frozenset({TIPO_QR, TIPO_PN, TIPO_CUENTA})


class _AvisoMalFormado(Exception):
    """El cuerpo no trae un aviso que se pueda leer."""


@dataclass(frozen=True)
class _AvisoCuenta:
    bank_account_id: str
    codi_status: str


@dataclass(frozen=True)
class _AvisoEntrante:
    tipo: str
    transaction_id: str
    aviso: AvisoPago | None
    cuenta: _AvisoCuenta | None = None
    bank_account_id: str = ""
    fecha_pago: object = None


def _respuesta(cuerpo: dict, status: int) -> JsonResponse:
    return JsonResponse(
        cuerpo,
        status=status,
        json_dumps_params={"ensure_ascii": False},
    )


def _a_decimal(valor: object) -> Decimal:
    if isinstance(valor, bool):
        raise ValueError
    if isinstance(valor, Decimal):
        return valor
    if isinstance(valor, int):
        return Decimal(str(valor))
    raise ValueError


def _monto_de_aviso(valor: object) -> Decimal:
    try:
        monto = _a_decimal(valor)
    except (InvalidOperation, ValueError, ArithmeticError) as exc:
        raise _AvisoMalFormado from exc
    exponente = monto.as_tuple().exponent
    if (
        not isinstance(exponente, int)
        or not monto.is_finite()
        or monto <= 0
        or exponente < -2
        or monto >= _MONTO_MAXIMO
    ):
        raise _AvisoMalFormado
    return monto


def _transaction_id_usable(valor: object) -> str | None:
    if (not isinstance(valor, str) or not valor.strip()
            or len(valor) > _LARGO_TRANSACTION_ID):
        return None
    return valor


def _objeto_json(cuerpo: bytes) -> dict:
    try:
        datos = json.loads(cuerpo, parse_float=Decimal)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        raise _AvisoMalFormado from exc
    if not isinstance(datos, dict):
        raise _AvisoMalFormado
    return datos


def _fecha_pago(valor):
    """Lee una fecha informativa sin rechazar el pago."""
    try:
        if isinstance(valor, (int, float, Decimal)) and not isinstance(valor, bool):
            return datetime.fromtimestamp(float(valor), tz=zona_utc.utc)
        if isinstance(valor, str):
            fecha = parse_datetime(valor)
            return fecha if fecha is not None and not timezone.is_naive(fecha) else None
    except (OverflowError, OSError, ValueError):
        return None
    return None


def _leer_aviso(cuerpo: bytes) -> _AvisoEntrante:
    datos = _objeto_json(cuerpo)
    tipo = datos.get("type")
    if not isinstance(tipo, str) or not tipo.strip() or len(tipo) > _LARGO_TIPO:
        raise _AvisoMalFormado

    transaction_id = _transaction_id_usable(datos.get("transactionId"))
    if tipo == TIPO_CUENTA:
        cuenta = _cuenta_de_aviso(datos)
        return _AvisoEntrante(
            tipo=tipo,
            transaction_id=cuenta.bank_account_id[:_LARGO_TRANSACTION_ID],
            aviso=None,
            cuenta=cuenta,
        )
    if tipo not in _TIPOS_CONOCIDOS:
        return _AvisoEntrante(
            tipo=tipo,
            transaction_id=transaction_id or "",
            aviso=None,
        )
    if transaction_id is None or "amount" not in datos:
        raise _AvisoMalFormado

    codi_qr_id = datos.get("codiQrId")
    if codi_qr_id == "":
        codi_qr_id = None
    if codi_qr_id is not None and (
        not isinstance(codi_qr_id, str) or len(codi_qr_id) > 64
    ):
        raise _AvisoMalFormado
    concepto = datos.get("concept") or ""
    if not isinstance(concepto, str):
        raise _AvisoMalFormado

    bank = datos.get("bankAccountId", "")
    if not isinstance(bank, str) or (bank and not re.fullmatch(
        r"[0-9A-HJKMNP-TV-Z]{26}", bank
    )):
        raise _AvisoMalFormado
    fecha = _fecha_pago(datos.get("datePaid"))

    return _AvisoEntrante(
        tipo=tipo,
        transaction_id=transaction_id,
        bank_account_id=bank,
        fecha_pago=fecha,
        aviso=AvisoPago(
            tipo=tipo,
            monto=_monto_de_aviso(datos["amount"]),
            transaction_id=transaction_id,
            codi_qr_id=codi_qr_id,
            concepto=concepto,
        ),
    )


def _registrar(webhook_id: str, tipo: str, resultado: str) -> None:
    logger.info(
        "aviso pey webhook_id=%s type=%s resultado=%s",
        webhook_id,
        tipo,
        resultado,
    )


def _cerrar(
    recibido: AvisoRecibido,
    *,
    webhook_id: str,
    tipo: str,
    resultado: str,
    movimiento: Movimiento | None = None,
) -> JsonResponse:
    recibido.resultado = resultado
    recibido.movimiento = movimiento
    recibido.save(update_fields=["resultado", "movimiento"])
    if resultado == AvisoRecibido.Resultado.SIN_COBRO:
        logger.warning(
            "aviso pey sin cobro type=%s webhook_id=%s transaction_id=%s",
            tipo,
            webhook_id,
            recibido.transaction_id,
        )
    elif resultado == AvisoRecibido.Resultado.MONTO_DISTINTO:
        logger.warning(
            "aviso pey webhook_id=%s type=%s resultado=%s",
            webhook_id,
            tipo,
            resultado,
        )
    else:
        _registrar(webhook_id, tipo, resultado)
    return _respuesta({"estado": resultado}, 200)


def _cuenta_de_aviso(datos: dict) -> _AvisoCuenta:
    bank = datos.get("bankAccountId")
    estado = datos.get("codiStatus")
    if not isinstance(bank, str):
        bank = ""
    if not isinstance(estado, str):
        estado = ""
    return _AvisoCuenta(bank_account_id=bank.strip(), codi_status=estado.strip())


def _aplicar_activacion_cuenta(
    recibido: AvisoRecibido,
    cuenta: _AvisoCuenta,
    webhook_id: str,
) -> JsonResponse:
    destino = None
    if cuenta.codi_status == "ACTIVE" and cuenta.bank_account_id:
        destino = CuentaCobro.objects.filter(
            pey_bank_account_id=cuenta.bank_account_id
        ).first()
    if destino is None:
        resultado = AvisoRecibido.Resultado.SIN_COBRO
    else:
        encolar_sync(destino, origen="webhook")
        resultado = AvisoRecibido.Resultado.APLICADO
    return _cerrar(recibido, webhook_id=webhook_id, tipo=recibido.tipo,
                   resultado=resultado)


def _procesar_aviso_registrado(
    *,
    recibido: AvisoRecibido,
    entrada: _AvisoEntrante,
    webhook_id: str,
    origen: Movimiento.Origen,
) -> JsonResponse:
    if entrada.cuenta is not None:
        return _aplicar_activacion_cuenta(recibido, entrada.cuenta, webhook_id)
    if entrada.aviso is None:
        return _cerrar(
            recibido,
            webhook_id=webhook_id,
            tipo=entrada.tipo,
            resultado=AvisoRecibido.Resultado.TIPO_DESCONOCIDO,
        )

    from pedidos.servicios.pagos import aplicar_pago

    aplicar_pago(recibido)
    recibido.refresh_from_db()
    if recibido.resultado in ("pendiente_correlacion", "monto_distinto"):
        logger.warning(
            "aviso pey webhook_id=%s type=%s resultado=%s transaction_id=%s",
            webhook_id, recibido.tipo, recibido.resultado, recibido.transaction_id,
        )
    else:
        _registrar(webhook_id, recibido.tipo, recibido.resultado)
    return _respuesta({"estado": recibido.resultado}, 200)


def _recibir_aviso_http(
    request: HttpRequest,
    *,
    origen: Movimiento.Origen,
) -> JsonResponse:
    webhook_id = request.headers.get("webhook-id", "")
    if not webhook_id or len(webhook_id) > _LARGO_WEBHOOK_ID:
        logger.warning("aviso rechazado webhook_id=%s", webhook_id)
        return _respuesta({"detalle": "aviso inválido"}, 400)

    try:
        entrada = _leer_aviso(request.body)
    except _AvisoMalFormado:
        logger.warning("aviso rechazado webhook_id=%s", webhook_id)
        return _respuesta({"detalle": "aviso inválido"}, 400)

    with transaction.atomic():
        try:
            with transaction.atomic():
                recibido = AvisoRecibido.objects.create(
                    webhook_id=webhook_id,
                    tipo=entrada.tipo,
                    transaction_id=entrada.transaction_id,
                    payload_hash=hashlib.sha256(request.body).hexdigest(),
                    monto=entrada.aviso.monto if entrada.aviso else None,
                    codi_qr_id=(entrada.aviso.codi_qr_id or "")
                    if entrada.aviso else "",
                    bank_account_id=entrada.bank_account_id,
                    fecha_pago=entrada.fecha_pago,
                    verificado_en=timezone.now(),
                    origen=origen,
                )
        except IntegrityError:
            _registrar(webhook_id, entrada.tipo, "duplicado")
            return _respuesta({"estado": "duplicado"}, 200)

        return _procesar_aviso_registrado(
            recibido=recibido,
            entrada=entrada,
            webhook_id=webhook_id,
            origen=origen,
        )


@csrf_exempt
@require_POST
def recibir_aviso_pey(request: HttpRequest) -> JsonResponse:
    try:
        verificar_firma(request.body, request.headers)
    except FirmaInvalida:
        logger.warning(
            "firma inválida en aviso pey webhook_id=%s",
            request.headers.get("webhook-id", ""),
        )
        return _respuesta({"detalle": "firma inválida"}, 401)

    webhook_id = request.headers.get("webhook-id", "")
    if not webhook_id or len(webhook_id) > _LARGO_WEBHOOK_ID:
        logger.warning("aviso pey rechazado webhook_id=%s", webhook_id)
        return _respuesta({"detalle": "aviso inválido"}, 400)

    return _recibir_aviso_http(
        request,
        origen=Movimiento.Origen.ORIGEN_PEY,
    )


@csrf_exempt
@require_POST
def recibir_aviso_desarrollo(
    request: HttpRequest,
) -> HttpResponseNotFound | JsonResponse:
    try:
        if modo_adaptador() != "desarrollo":
            return HttpResponseNotFound()
    except ImproperlyConfigured:
        return HttpResponseNotFound()

    return _recibir_aviso_http(
        request,
        origen=Movimiento.Origen.ORIGEN_DESARROLLO,
    )
