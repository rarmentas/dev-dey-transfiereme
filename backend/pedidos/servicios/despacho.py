"""Envío durable de intentos, con red fuera de transacciones."""

import logging
import re
import uuid
from datetime import timedelta
from decimal import Decimal

from config.modo import cobro_habilitado, demo_activo, politica_cobro_version
from django.db import connection, transaction
from django.db.models import F
from django.utils import timezone
from movimientos.models import Cobro, Movimiento
from pey.desarrollo import AdaptadorDesarrollo
from pey.seleccion import obtener_puerto
from pey.tipos import ErrorPey, ParametroInvalido

from pedidos.contratos.v1 import TipoEvento
from pedidos.models import IntentoCobro
from pedidos.servicios.candados import bloquear_para_pago
from pedidos.servicios.cobros import descartar


logger = logging.getLogger(__name__)


def _bloquear(intento):
    return bloquear_para_pago(
        intento.comercio_id,
        intento.pedido_id,
        intento.pk,
        intento.cuenta_id,
        intento.cobro_id,
    )


def _evento(comercio, pedido, intento, tipo):
    if pedido:
        from pedidos.servicios.eventos import emitir

        pedido.version += 1
        pedido.save(update_fields=["version", "actualizado_en"])
        evento = emitir(comercio, pedido, tipo, intento=intento)
        if tipo == TipoEvento.COBRO_PENDIENTE and intento.cobro_id:
            evento.snapshot["qr_string"] = intento.cobro.qr_string or None
            evento.snapshot["vence_en"] = intento.cobro.vence_en.isoformat()
            evento.save(update_fields=["snapshot"])


def enviar_intento(intento_id, puerto=None):
    if connection.in_atomic_block:
        raise RuntimeError("El envío debe comenzar fuera de una transacción.")
    referencia = IntentoCobro.objects.filter(pk=intento_id).first()
    if not referencia:
        return None
    with transaction.atomic():
        comercio, pedido, intento, cuenta, _, _ = _bloquear(referencia)
        if intento.estado != "reservado":
            return intento
        if intento.origen == "pedido" and not cobro_habilitado():
            return intento
        if (intento.demo_mode, intento.politica_cobro_version) != (
            demo_activo(),
            politica_cobro_version(),
        ):
            descartar(intento, "condiciones_cambiaron")
            intento.refresh_from_db()
            return intento
        if intento.origen == "pedido":
            cot = intento.cotizacion
            if (
                not pedido
                or pedido.estado != "aceptado"
                or pedido.revision_vigente != cot.revision
            ):
                descartar(intento, "condiciones_cambiaron")
                intento.refresh_from_db()
                return intento
        if intento.demo_mode:
            from django.conf import settings

            if (
                not demo_activo()
                or intento.importe_efectivo_centavos != 1
                or intento.pey_bank_account_id != settings.DEMO_PEY_BANK_ACCOUNT_ID
            ):
                descartar(intento, "destino_demo_invalido")
                intento.refresh_from_db()
                return intento
        token = uuid.uuid4()
        n = IntentoCobro.objects.filter(
            pk=intento.pk, estado="reservado", version=intento.version
        ).update(
            estado="enviando",
            version=F("version") + 1,
            token_envio=token,
            envio_iniciado_en=timezone.now(),
        )
        if not n:
            return None
    if puerto is None:
        puerto = obtener_puerto()
    args = dict(
        monto=Decimal(intento.importe_efectivo_centavos) / 100,
        concepto=intento.concepto,
        expiracion_s=intento.expiracion_s,
        num_ref=intento.referencia,
        bank_account_id=intento.pey_bank_account_id,
    )
    try:
        if intento.canal == "qr_venta":
            respuesta = puerto.crear_qr(**args)
            if not respuesta.id or not respuesta.qr_string:
                raise ValueError("Respuesta ilegible")
        else:
            respuesta = puerto.crear_notificacion(
                telefono=intento.telefono_bancario, **args
            )
            if not respuesta.transaction_id:
                raise ValueError("Respuesta ilegible")
    except Exception as exc:
        definitivo = (
            isinstance(exc, ParametroInvalido)
            or isinstance(exc, ErrorPey)
            and not exc.puede_haberse_creado
        )
        estado = "rechazado" if definitivo else "incierto"
        with transaction.atomic():
            comercio, pedido, actual, _, _, _ = _bloquear(intento)
            n = IntentoCobro.objects.filter(
                pk=actual.pk, estado="enviando", token_envio=token
            ).update(
                estado=estado,
                version=F("version") + 1,
                error=(
                    exc.tipo
                    if isinstance(exc, ErrorPey)
                    and re.fullmatch(r"[A-Z0-9_]{1,50}", exc.tipo)
                    else type(exc).__name__
                ),
                request_id=(
                    exc.request_id
                    if isinstance(exc, ErrorPey)
                    and isinstance(exc.request_id, str)
                    and re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", exc.request_id)
                    else ""
                ),
                telefono_bancario="" if definitivo else actual.telefono_bancario,
            )
            if n:
                actual.estado = estado
                _evento(
                    comercio,
                    pedido,
                    actual,
                    TipoEvento.COBRO_RECHAZADO
                    if definitivo
                    else TipoEvento.COBRO_INCIERTO,
                )
        return IntentoCobro.objects.get(pk=intento.pk)
    with transaction.atomic():
        comercio, pedido, actual, cuenta, _, _ = _bloquear(intento)
        if actual.estado != "enviando" or actual.token_envio != token:
            return actual
        vence = timezone.now() + timedelta(seconds=actual.expiracion_s)
        cobro = Cobro.objects.create(
            comercio=comercio,
            cuenta=cuenta,
            canal=actual.canal,
            monto=args["monto"],
            concepto=actual.concepto,
            vence_en=vence,
            pey_bank_account_id=actual.pey_bank_account_id,
            pey_qr_id=respuesta.id if actual.canal == "qr_venta" else None,
            qr_string=respuesta.qr_string if actual.canal == "qr_venta" else "",
            pey_transaction_id=(
                respuesta.transaction_id if actual.canal == "notificacion" else None
            ),
        )
        Movimiento.objects.create(
            comercio=comercio,
            cobro=cobro,
            canal=actual.canal,
            monto=args["monto"],
            concepto=actual.concepto,
            estado="pendiente",
            origen=(
                "origen_desarrollo"
                if isinstance(puerto, AdaptadorDesarrollo)
                else "origen_pey"
            ),
        )
        IntentoCobro.objects.filter(
            pk=actual.pk, estado="enviando", token_envio=token
        ).update(
            estado="pendiente",
            cobro=cobro,
            enviado_en=timezone.now(),
            telefono_bancario="",
            version=F("version") + 1,
        )
        actual.estado = "pendiente"
        actual.cobro = cobro
        _evento(comercio, pedido, actual, TipoEvento.COBRO_PENDIENTE)
        try:
            from pedidos.servicios.pagos import reaplicar_pendientes

            with transaction.atomic():
                reaplicar_pendientes(cobro)
        except Exception:
            logger.warning("No se pudo reaplicar el aviso cobro_id=%s", cobro.pk)
    return IntentoCobro.objects.get(pk=intento.pk)


def recuperar_intentos_abandonados():
    limite = timezone.now() - timedelta(seconds=60)
    ids = list(
        IntentoCobro.objects.filter(
            estado="enviando", envio_iniciado_en__lt=limite
        ).values_list("pk", flat=True)
    )
    for pk in ids:
        referencia = IntentoCobro.objects.get(pk=pk)
        with transaction.atomic():
            comercio, pedido, actual, _, _, _ = _bloquear(referencia)
            if actual.estado == "enviando" and actual.envio_iniciado_en < limite:
                IntentoCobro.objects.filter(pk=pk, estado="enviando").update(
                    estado="incierto",
                    error="envio_abandonado",
                    version=F("version") + 1,
                )
                actual.estado = "incierto"
                _evento(comercio, pedido, actual, TipoEvento.COBRO_INCIERTO)
    reservas = list(
        IntentoCobro.objects.filter(
            origen="legado", estado="reservado", creado_en__lt=limite
        )
    )
    for referencia in reservas:
        with transaction.atomic():
            _, _, intento, _, _, _ = _bloquear(referencia)
            if intento.estado == "reservado" and intento.creado_en < limite:
                IntentoCobro.objects.filter(
                    pk=intento.pk, estado="reservado", version=intento.version
                ).update(
                    estado="descartado",
                    motivo_descarte="reserva_abandonada",
                    telefono_bancario="",
                    version=F("version") + 1,
                )


def ciclo(puerto=None):
    from ambito.operaciones_cuenta import ejecutar_pendientes, recuperar_abandonadas

    recuperar_abandonadas()
    ejecutar_pendientes()
    recuperar_intentos_abandonados()
    from ambito.models import Comercio
    from canales.models import LatidoCanal
    from ventas.canal import vencer_pendientes

    vencidos = (
        Movimiento.objects.filter(
            estado="pendiente",
            canal__in=["qr_venta", "notificacion"],
            cobro__vence_en__lte=timezone.now(),
        )
        .values_list("comercio_id", flat=True)
        .distinct()
    )
    for comercio in Comercio.objects.filter(pk__in=vencidos):
        vencer_pendientes(comercio)

    LatidoCanal.objects.get_or_create(
        proceso="procesar_cobros", defaults={"ultimo_ciclo": timezone.now()}
    )
    LatidoCanal.objects.filter(proceso="procesar_cobros").update(
        ultimo_ciclo=timezone.now(), ciclos=F("ciclos") + 1
    )
    if not cobro_habilitado():
        return
    ids = list(
        IntentoCobro.objects.filter(origen="pedido", estado="reservado")
        .order_by("creado_en")
        .values_list("pk", flat=True)
    )
    for pk in ids:
        enviar_intento(pk, puerto)
