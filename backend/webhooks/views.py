"""Puerto HTTP del aviso de pey. No llama a pey."""

import json
import logging
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.db import IntegrityError, transaction
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from movimientos.correlacion import TIPO_PN, TIPO_QR, AvisoPago, aplicar_aviso
from movimientos.exceptions import (
    AvisoDuplicado,
    AvisoInvalido,
    AvisoSinCobro,
    MontoDistinto,
    TransicionInvalida,
)
from movimientos.models import Movimiento
from webhooks.models import AvisoRecibido
from webhooks.verificacion import FirmaInvalida, verificar_firma

logger = logging.getLogger(__name__)

_LARGO_WEBHOOK_ID = 128
_LARGO_TIPO = 128
_LARGO_TRANSACTION_ID = 64
_MONTO_MAXIMO = Decimal(10) ** 10
_TIPOS_CONOCIDOS = frozenset({TIPO_QR, TIPO_PN})


class _AvisoMalFormado(Exception):
    """El cuerpo no trae un aviso que se pueda leer."""


@dataclass(frozen=True)
class _AvisoEntrante:
    tipo: str
    transaction_id: str
    aviso: AvisoPago | None


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
    if not isinstance(valor, str) or not valor.strip() or len(valor) > _LARGO_TRANSACTION_ID:
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


def _leer_aviso(cuerpo: bytes) -> _AvisoEntrante:
    datos = _objeto_json(cuerpo)
    tipo = datos.get("type")
    if not isinstance(tipo, str) or not tipo.strip() or len(tipo) > _LARGO_TIPO:
        raise _AvisoMalFormado

    transaction_id = _transaction_id_usable(datos.get("transactionId"))
    if tipo not in _TIPOS_CONOCIDOS:
        return _AvisoEntrante(
            tipo=tipo,
            transaction_id=transaction_id or "",
            aviso=None,
        )
    if transaction_id is None or "amount" not in datos:
        raise _AvisoMalFormado

    codi_qr_id = datos.get("codiQrId") or None
    if codi_qr_id is not None and not isinstance(codi_qr_id, str):
        raise _AvisoMalFormado
    concepto = datos.get("concept") or ""
    if not isinstance(concepto, str):
        raise _AvisoMalFormado

    return _AvisoEntrante(
        tipo=tipo,
        transaction_id=transaction_id,
        aviso=AvisoPago(
            tipo=tipo,
            monto=_monto_de_aviso(datos["amount"]),
            transaction_id=transaction_id,
            codi_qr_id=codi_qr_id,
            concepto=concepto,
        ),
    )


def _es_choque_de_transaction_id(exc: IntegrityError) -> bool:
    causa = exc.__cause__
    diag = getattr(causa, "diag", None)
    nombre = getattr(diag, "constraint_name", None) or ""
    return "pey_transaction_id" in f"{nombre} {exc}".lower()


def _pago_ya_registrado(transaction_id: str) -> bool:
    return Movimiento.objects.filter(
        pey_transaction_id=transaction_id,
        estado=Movimiento.Estado.PAGADO,
    ).exists()


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
        entrada = _leer_aviso(request.body)
    except _AvisoMalFormado:
        logger.warning("aviso pey rechazado webhook_id=%s", webhook_id)
        return _respuesta({"detalle": "aviso inválido"}, 400)

    # El pagado y el registro del aviso quedan en la misma transacción.
    with transaction.atomic():
        try:
            with transaction.atomic():
                recibido = AvisoRecibido.objects.create(
                    webhook_id=webhook_id,
                    tipo=entrada.tipo,
                    transaction_id=entrada.transaction_id,
                )
        except IntegrityError:
            _registrar(webhook_id, entrada.tipo, "duplicado")
            return _respuesta({"estado": "duplicado"}, 200)

        if entrada.aviso is None:
            return _cerrar(
                recibido,
                webhook_id=webhook_id,
                tipo=entrada.tipo,
                resultado=AvisoRecibido.Resultado.TIPO_DESCONOCIDO,
            )

        aviso = entrada.aviso
        if _pago_ya_registrado(aviso.transaction_id):
            return _cerrar(
                recibido,
                webhook_id=webhook_id,
                tipo=aviso.tipo,
                resultado=AvisoRecibido.Resultado.DUPLICADO_TRANSACCION,
            )

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
        except AvisoDuplicado:
            resultado = AvisoRecibido.Resultado.DUPLICADO_TRANSACCION
        except MontoDistinto:
            resultado = AvisoRecibido.Resultado.MONTO_DISTINTO
        except AvisoSinCobro:
            resultado = AvisoRecibido.Resultado.SIN_COBRO
        except TransicionInvalida:
            resultado = AvisoRecibido.Resultado.TRANSICION_INVALIDA
        except AvisoInvalido:
            resultado = AvisoRecibido.Resultado.TIPO_DESCONOCIDO
        else:
            resultado = AvisoRecibido.Resultado.APLICADO

        return _cerrar(
            recibido,
            webhook_id=webhook_id,
            tipo=aviso.tipo,
            resultado=resultado,
            movimiento=movimiento,
        )
