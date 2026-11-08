"""Puerto HTTP del aviso de pey. No llama a pey."""

import json
import logging
from decimal import Decimal, InvalidOperation

from django.db import IntegrityError, transaction
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from movimientos.correlacion import AvisoPago, aplicar_aviso
from movimientos.exceptions import AvisoInvalido, AvisoSinCobro, TransicionInvalida
from movimientos.models import Movimiento
from webhooks.models import AvisoRecibido
from webhooks.verificacion import FirmaInvalida, verificar_firma

logger = logging.getLogger(__name__)

_LARGO_WEBHOOK_ID = 128
_LARGO_TIPO = 128
_LARGO_TRANSACTION_ID = 64


class _AvisoMalFormado(Exception):
    """El cuerpo no trae un aviso que se pueda leer."""


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


def _leer_aviso(cuerpo: bytes) -> AvisoPago:
    try:
        datos = json.loads(cuerpo, parse_float=Decimal)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        raise _AvisoMalFormado from exc
    if not isinstance(datos, dict):
        raise _AvisoMalFormado

    tipo = datos.get("type")
    transaction_id = datos.get("transactionId")
    if (
        not isinstance(tipo, str)
        or not tipo.strip()
        or len(tipo) > _LARGO_TIPO
        or not isinstance(transaction_id, str)
        or not transaction_id.strip()
        or len(transaction_id) > _LARGO_TRANSACTION_ID
        or "amount" not in datos
    ):
        raise _AvisoMalFormado

    try:
        monto = _a_decimal(datos["amount"])
    except (InvalidOperation, ValueError, ArithmeticError) as exc:
        raise _AvisoMalFormado from exc

    codi_qr_id = datos.get("codiQrId") or None
    if codi_qr_id is not None and not isinstance(codi_qr_id, str):
        raise _AvisoMalFormado
    concepto = datos.get("concept") or ""
    if not isinstance(concepto, str):
        raise _AvisoMalFormado

    return AvisoPago(
        tipo=tipo,
        monto=monto,
        transaction_id=transaction_id,
        codi_qr_id=codi_qr_id,
        concepto=concepto,
    )


def _es_choque_de_transaction_id(exc: IntegrityError) -> bool:
    causa = exc.__cause__
    diag = getattr(causa, "diag", None)
    nombre = getattr(diag, "constraint_name", None) or ""
    return "pey_transaction_id" in f"{nombre} {exc}".lower()


def _registrar(webhook_id: str, tipo: str, resultado: str) -> None:
    logger.info(
        "aviso pey webhook_id=%s type=%s resultado=%s",
        webhook_id,
        tipo,
        resultado,
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

    try:
        aviso = _leer_aviso(request.body)
    except _AvisoMalFormado:
        logger.warning("aviso pey rechazado webhook_id=%s", webhook_id)
        return _respuesta({"detalle": "aviso inválido"}, 400)

    # El pagado y el registro del aviso quedan en la misma transacción.
    with transaction.atomic():
        try:
            with transaction.atomic():
                recibido = AvisoRecibido.objects.create(
                    webhook_id=webhook_id,
                    tipo=aviso.tipo,
                    transaction_id=aviso.transaction_id,
                )
        except IntegrityError:
            _registrar(webhook_id, aviso.tipo, "duplicado")
            return _respuesta({"estado": "duplicado"}, 200)

        if Movimiento.objects.filter(pey_transaction_id=aviso.transaction_id).exists():
            recibido.resultado = AvisoRecibido.Resultado.DUPLICADO_TRANSACCION
            recibido.save(update_fields=["resultado"])
            _registrar(webhook_id, aviso.tipo, recibido.resultado)
            return _respuesta({"estado": recibido.resultado}, 200)

        movimiento = None
        try:
            with transaction.atomic():
                movimiento = aplicar_aviso(
                    aviso,
                    origen=Movimiento.Origen.ORIGEN_PEY,
                )
        except IntegrityError as exc:
            if not _es_choque_de_transaction_id(exc):
                raise
            resultado = AvisoRecibido.Resultado.DUPLICADO_TRANSACCION
            movimiento = None
        except AvisoSinCobro:
            resultado = AvisoRecibido.Resultado.SIN_COBRO
        except TransicionInvalida:
            resultado = AvisoRecibido.Resultado.TRANSICION_INVALIDA
        except AvisoInvalido:
            resultado = AvisoRecibido.Resultado.TIPO_DESCONOCIDO
        else:
            resultado = AvisoRecibido.Resultado.APLICADO

        recibido.resultado = resultado
        recibido.movimiento = movimiento
        recibido.save(update_fields=["resultado", "movimiento"])
        _registrar(webhook_id, aviso.tipo, resultado)

    return _respuesta({"estado": resultado}, 200)
