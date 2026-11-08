"""Alta de una venta por QR. No habla con la red: usa el puerto inyectado."""

import logging
import re
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal, DecimalException, InvalidOperation, localcontext

from django.db import transaction
from django.utils import timezone

from ambito.models import Comercio
from movimientos.models import Cobro, Movimiento
from pey.desarrollo import AdaptadorDesarrollo
from pey.produccion import AdaptadorProduccion
from pey.puerto import PuertoPey
from pey.seleccion import obtener_puerto
from ventas.canal import exigir_sin_venta_viva, vencer_pendientes

logger = logging.getLogger(__name__)

VENTA_EXPIRACION_S = 600

_NUM_REF = re.compile(r"^[0-9]{1,7}$")
_TELEFONO = re.compile(r"^[0-9]{10}$")
_CERO = Decimal("0")
_CENTAVO = Decimal("0.01")
# Exclusivo. El QR de pey no admite 10**10 ni más.
_TOPE_MONTO = Decimal("10000000000")
# Inclusivo. La notificación de pey no pasa de 1 000 000.
_TOPE_NOTIFICACION = Decimal("1000000")
_PREC_MONTO = 50
_CONCEPTO_VACIO = "Transferencia"
# Mismo tope que Movimiento.concepto y Cobro.concepto (max_length=500).
_LARGO_CONCEPTO = 500
_REF_VACIA = "0"


class ValidacionVenta(Exception):
    """El alta no cumple el contrato. No se llamó al puerto."""

    def __init__(self, campo: str, mensaje: str) -> None:
        self.campo = campo
        super().__init__(mensaje)


class ReferenciaInvalida(ValidacionVenta):
    """La referencia trae algo que no es vacío ni 1–7 dígitos."""

    def __init__(self) -> None:
        super().__init__(
            "referencia",
            "La referencia debe ser numérica, de 1 a 7 dígitos.",
        )


class MontoInvalido(ValidacionVenta):
    def __init__(self, mensaje: str) -> None:
        super().__init__("monto", mensaje)


class ConceptoInvalido(ValidacionVenta):
    def __init__(self, mensaje: str) -> None:
        super().__init__("concepto", mensaje)


class TelefonoInvalido(ValidacionVenta):
    """El teléfono no es de 10 dígitos. No se llamó al puerto."""

    def __init__(self) -> None:
        super().__init__("telefono", "El teléfono debe ser de 10 dígitos.")


class CuentaNoActive(Exception):
    """El puerto dice que la cuenta no está ACTIVE. No se crea el QR."""


@dataclass(frozen=True)
class VentaCreada:
    movimiento: Movimiento
    cobro: Cobro
    qr_string: str
    transaction_id: str = ""


def crear_venta_qr(
    *,
    comercio: Comercio,
    monto: Decimal,
    concepto: str,
    referencia: str,
    puerto: PuertoPey | None = None,
) -> VentaCreada:
    """Valida, pide el QR y solo entonces persiste cobro y movimiento."""
    referencia_ok = _referencia(referencia)
    monto_ok = _monto(monto)
    concepto_ok = _concepto(concepto)

    if puerto is None:
        puerto = obtener_puerto()

    origen = _origen(puerto)
    # Fuera del candado: un ErrorPey no revierte estos vencidos.
    vencer_pendientes(comercio)
    # El candado del comercio se sostiene durante la llamada a pey (timeout
    # 10 s) a propósito: dos altas simultáneas no abren dos cobros (C12).
    qr = None
    try:
        with transaction.atomic():
            exigir_sin_venta_viva(comercio)
            if not puerto.cuenta_active(comercio):
                raise CuentaNoActive()
            cuenta = _cuenta_de_produccion(puerto, comercio)
            qr = puerto.crear_qr(
                monto=monto_ok,
                concepto=concepto_ok,
                expiracion_s=VENTA_EXPIRACION_S,
                num_ref=referencia_ok,
                **cuenta,
            )
            vence_en = timezone.now() + timedelta(seconds=VENTA_EXPIRACION_S)
            cobro = Cobro.objects.create(
                comercio=comercio,
                canal=Movimiento.Canal.QR_VENTA,
                monto=monto_ok,
                concepto=concepto_ok,
                vence_en=vence_en,
                pey_qr_id=qr.id,
                qr_string=qr.qr_string,
                pey_bank_account_id=cuenta.get("bank_account_id", ""),
            )
            movimiento = Movimiento.objects.create(
                comercio=comercio,
                cobro=cobro,
                canal=Movimiento.Canal.QR_VENTA,
                monto=monto_ok,
                concepto=concepto_ok,
                estado=Movimiento.Estado.PENDIENTE,
                origen=origen,
            )
    except Exception:
        # Si la base falla, el QR ya existe en pey pero qr_string no se entrega.
        if qr is not None:
            logger.error(
                "qr de venta creado en pey sin persistir pey_qr_id=%s comercio_id=%s",
                qr.id,
                comercio.pk,
            )
        raise
    return VentaCreada(movimiento=movimiento, cobro=cobro, qr_string=qr.qr_string)


def crear_venta_notificacion(
    *,
    comercio: Comercio,
    monto: Decimal,
    telefono: str,
    concepto: str,
    referencia: str,
    puerto: PuertoPey | None = None,
) -> VentaCreada:
    """Valida, pide la notificación y solo entonces persiste cobro y movimiento."""
    telefono_ok = _telefono(telefono)
    monto_ok = _monto(monto, tope=_TOPE_NOTIFICACION, exclusivo=False)
    referencia_ok = _referencia(referencia)
    concepto_ok = _concepto(concepto)

    if puerto is None:
        puerto = obtener_puerto()

    origen = _origen(puerto)
    # Fuera del candado: un ErrorPey no revierte estos vencidos.
    vencer_pendientes(comercio)
    aviso = None
    try:
        with transaction.atomic():
            exigir_sin_venta_viva(comercio)
            if not puerto.cuenta_active(comercio):
                raise CuentaNoActive()
            cuenta = _cuenta_de_produccion(puerto, comercio)
            aviso = puerto.crear_notificacion(
                monto=monto_ok,
                telefono=telefono_ok,
                concepto=concepto_ok,
                expiracion_s=VENTA_EXPIRACION_S,
                num_ref=referencia_ok,
                **cuenta,
            )
            vence_en = timezone.now() + timedelta(seconds=VENTA_EXPIRACION_S)
            cobro = Cobro.objects.create(
                comercio=comercio,
                canal=Movimiento.Canal.NOTIFICACION,
                monto=monto_ok,
                concepto=concepto_ok,
                vence_en=vence_en,
                pey_transaction_id=aviso.transaction_id,
                pey_bank_account_id=cuenta.get("bank_account_id", ""),
            )
            movimiento = Movimiento.objects.create(
                comercio=comercio,
                cobro=cobro,
                canal=Movimiento.Canal.NOTIFICACION,
                monto=monto_ok,
                concepto=concepto_ok,
                estado=Movimiento.Estado.PENDIENTE,
                origen=origen,
            )
    except Exception:
        # El teléfono completo no se escribe: como mucho los 4 últimos.
        if aviso is not None:
            logger.error(
                "notificación de venta creada en pey sin persistir "
                "transaction_id=%s comercio_id=%s telefono_final=%s",
                aviso.transaction_id,
                comercio.pk,
                telefono_ok[-4:],
            )
        raise
    logger.info(
        "venta por notificación comercio_id=%s transaction_id=%s telefono_final=%s",
        comercio.pk,
        aviso.transaction_id,
        telefono_ok[-4:],
    )
    return VentaCreada(
        movimiento=movimiento,
        cobro=cobro,
        qr_string="",
        transaction_id=aviso.transaction_id,
    )


def _cuenta_de_produccion(puerto: PuertoPey, comercio: Comercio) -> dict[str, str]:
    """En producción el cobro va a la cuenta del comercio. En desarrollo no se exige."""
    if not isinstance(puerto, AdaptadorProduccion):
        return {}
    ident = (comercio.pey_bank_account_id or "").strip()
    if not ident:
        raise CuentaNoActive()
    return {"bank_account_id": ident}


def _origen(puerto: PuertoPey) -> str:
    if isinstance(puerto, AdaptadorDesarrollo):
        return Movimiento.Origen.ORIGEN_DESARROLLO
    return Movimiento.Origen.ORIGEN_PEY


def _referencia(referencia: str | None) -> str:
    if referencia is None or referencia == "":
        return _REF_VACIA
    if not isinstance(referencia, str) or _NUM_REF.fullmatch(referencia) is None:
        raise ReferenciaInvalida()
    return referencia


def _monto(
    monto: Decimal,
    *,
    tope: Decimal = _TOPE_MONTO,
    exclusivo: bool = True,
) -> Decimal:
    if not isinstance(monto, Decimal):
        raise MontoInvalido("El monto debe ser un número decimal.")
    try:
        with localcontext() as ctx:
            ctx.prec = _PREC_MONTO
            ctx.traps[InvalidOperation] = True
            if not monto.is_finite():
                raise MontoInvalido("El monto debe ser un número finito.")
            if monto <= _CERO:
                raise MontoInvalido("El monto debe ser mayor que 0.")
            exponente = monto.as_tuple().exponent
            if not isinstance(exponente, int) or exponente < -2:
                raise MontoInvalido("El monto no admite más de 2 decimales.")
            if exclusivo:
                if monto >= tope:
                    raise MontoInvalido("El monto no cabe en el QR.")
            elif monto > tope:
                raise MontoInvalido("El monto no puede pasar de 1000000.")
            return monto.quantize(_CENTAVO)
    except DecimalException as exc:
        raise MontoInvalido("El monto no se puede representar.") from exc


def _telefono(telefono: str) -> str:
    if not isinstance(telefono, str) or _TELEFONO.fullmatch(telefono) is None:
        raise TelefonoInvalido()
    return telefono


def _concepto(concepto: str | None) -> str:
    if concepto is None:
        return _CONCEPTO_VACIO
    if not isinstance(concepto, str):
        raise ConceptoInvalido("El concepto debe ser texto.")
    if concepto.strip() == "":
        return _CONCEPTO_VACIO
    if len(concepto) > _LARGO_CONCEPTO:
        raise ConceptoInvalido("El concepto no puede pasar de 500 caracteres.")
    return concepto
