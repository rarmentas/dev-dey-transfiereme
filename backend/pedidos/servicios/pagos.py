"""Correlación durable y aplicación atómica de avisos bancarios."""

import logging

from django.db import IntegrityError, transaction
from django.db.models import F
from movimientos.correlacion import TIPO_PN, TIPO_QR
from movimientos.models import Cobro, Movimiento
from webhooks.models import AvisoRecibido

from pedidos.contratos.v1 import TipoEvento
from pedidos.models import IntentoCobro
from pedidos.servicios.candados import bloquear_para_pago
from pedidos.servicios.eventos import emitir


def _localizar(aviso):
    if aviso.tipo == TIPO_QR and aviso.codi_qr_id:
        return Cobro.objects.filter(
            pey_qr_id=aviso.codi_qr_id, canal__in=["qr_general", "qr_venta"]
        ).first()
    if aviso.tipo == TIPO_PN and aviso.transaction_id:
        return Cobro.objects.filter(
            pey_transaction_id=aviso.transaction_id, canal="notificacion"
        ).first()
    return None


def _cerrar(aviso, resultado, correlacion, movimiento=None, razon=""):
    aviso.resultado = resultado
    aviso.correlacion = correlacion
    aviso.movimiento = movimiento
    aviso.razon = razon
    aviso.save(update_fields=["resultado", "correlacion", "movimiento", "razon"])
    return movimiento


def aplicar_pago(aviso):
    """Aplica una confirmación ya verificada, sin realizar llamadas de red."""
    cobro = _localizar(aviso)
    if not cobro:
        identificable = bool(
            aviso.codi_qr_id if aviso.tipo == TIPO_QR else aviso.transaction_id
        )
        resultado = "pendiente_correlacion" if identificable else "sin_cobro"
        correlacion = "pendiente" if identificable else "rechazado"
        AvisoRecibido.objects.filter(
            pk=aviso.pk, correlacion__in=["no_aplica", "pendiente"]
        ).update(resultado=resultado, correlacion=correlacion)
        aviso.refresh_from_db()
        return None
    intento = IntentoCobro.objects.filter(cobro_id=cobro.pk).first()
    movimiento_id = (
        cobro.movimientos.order_by("pk").values_list("pk", flat=True).first()
        if cobro.canal != "qr_general"
        else None
    )
    try:
        with transaction.atomic():
            comercio, pedido, intento, _, cobro, movimiento = bloquear_para_pago(
                cobro.comercio_id,
                intento.pedido_id if intento else None,
                intento.pk if intento else None,
                cobro.cuenta_id,
                cobro.pk,
                movimiento_id,
            )
            aviso = AvisoRecibido.objects.select_for_update().get(pk=aviso.pk)
            if aviso.resultado and aviso.correlacion != "pendiente":
                return aviso.movimiento
            if Movimiento.objects.filter(
                pey_transaction_id=aviso.transaction_id, estado="pagado"
            ).exists():
                return _cerrar(aviso, "duplicado_transaccion", "rechazado")
            if cobro.pey_bank_account_id and (
                cobro.pey_bank_account_id != aviso.bank_account_id
            ):
                return _cerrar(aviso, "destino_distinto", "rechazado")
            if cobro.canal != "qr_general" and aviso.monto != cobro.monto:
                return _cerrar(aviso, "monto_distinto", "rechazado")
            razon = (
                "" if cobro.pey_bank_account_id else "destino_historico_sin_snapshot"
            )
            if cobro.canal == "qr_general":
                movimiento = Movimiento.objects.create(
                    comercio=comercio,
                    cobro=cobro,
                    canal=cobro.canal,
                    monto=aviso.monto,
                    concepto=cobro.concepto,
                    estado="pagado",
                    origen=aviso.origen,
                    pey_transaction_id=aviso.transaction_id,
                )
            elif not movimiento:
                return _cerrar(aviso, "sin_cobro", "rechazado")
            elif movimiento.estado not in ("pendiente", "vencido"):
                return _cerrar(aviso, "transicion_invalida", "rechazado")
            else:
                estaba_vencido = movimiento.estado == "vencido"
                movimiento.cambiar_estado(Movimiento.Estado.PAGADO)
                movimiento.pey_transaction_id = aviso.transaction_id
                movimiento.save(update_fields=["pey_transaction_id", "actualizado_en"])
                if estaba_vencido:
                    logging.getLogger("movimientos.correlacion").warning(
                        "pago tardío movimiento_id=%s transaction_id=%s comercio_id=%s",
                        movimiento.pk,
                        aviso.transaction_id,
                        comercio.pk,
                    )
            if intento:
                if intento.estado not in ("pendiente", "vencido"):
                    raise ValueError("El intento no admite confirmación bancaria.")
                n = IntentoCobro.objects.filter(
                    pk=intento.pk, estado=intento.estado, version=intento.version
                ).update(estado="pagado", version=F("version") + 1)
                if n != 1:
                    raise RuntimeError("El intento cambió durante la confirmación.")
                if pedido:
                    pedido.version += 1
                    pedido.save(update_fields=["version", "actualizado_en"])
                    emitir(
                        comercio, pedido, TipoEvento.PAGO_CONFIRMADO, intento=intento
                    )
            return _cerrar(aviso, "aplicado", "correlacionado", movimiento, razon)
    except IntegrityError:
        if Movimiento.objects.filter(pey_transaction_id=aviso.transaction_id).exists():
            return _cerrar(aviso, "duplicado_transaccion", "rechazado")
        raise


def reaplicar_pendientes(cobro):
    filtros = (
        {"codi_qr_id": cobro.pey_qr_id}
        if cobro.canal != "notificacion"
        else {"transaction_id": cobro.pey_transaction_id}
    )
    for aviso in AvisoRecibido.objects.filter(correlacion="pendiente", **filtros):
        aplicar_pago(aviso)


def reaplicar_avisos_pendientes():
    for aviso in AvisoRecibido.objects.filter(correlacion="pendiente").iterator():
        try:
            aplicar_pago(aviso)
        except Exception:
            logging.getLogger(__name__).warning(
                "No se pudo reaplicar aviso_id=%s", aviso.pk
            )
