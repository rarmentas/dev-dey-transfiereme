"""Resuelve un intento incierto con evidencia proporcionada por el operador."""

import logging
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone
from movimientos.models import Cobro, Movimiento

from pedidos.contratos.v1 import TipoEvento
from pedidos.models import IntentoCobro
from pedidos.servicios.candados import bloquear_para_pago
from pedidos.servicios.despacho import _evento


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Registra la resolución de un cobro incierto sin confirmar pago."

    def add_arguments(self, parser):
        parser.add_argument("--intento", required=True)
        parser.add_argument("--accion", choices=["sin_cobro", "enlazar"], required=True)
        parser.add_argument("--qr-id")
        parser.add_argument("--transaction-id")
        parser.add_argument("--confirmar", action="store_true")

    def handle(self, *args, **opciones):
        if not opciones["confirmar"]:
            raise CommandError("Se requiere --confirmar y evidencia del operador.")
        try:
            referencia = IntentoCobro.objects.filter(pk=opciones["intento"]).first()
        except (ValueError, TypeError, ValidationError):
            referencia = None
        if not referencia:
            raise CommandError("Intento no encontrado.")
        try:
            with transaction.atomic():
                comercio, pedido, intento, cuenta, _, _ = bloquear_para_pago(
                    referencia.comercio_id,
                    referencia.pedido_id,
                    referencia.pk,
                    referencia.cuenta_id,
                )
                if intento.estado != "incierto":
                    raise CommandError("El intento no está incierto.")
                qr_id, tx_id = opciones["qr_id"], opciones["transaction_id"]
                if opciones["accion"] == "sin_cobro":
                    if qr_id or tx_id:
                        raise CommandError("sin_cobro no admite identificadores.")
                    IntentoCobro.objects.filter(pk=intento.pk).update(
                        estado="rechazado",
                        error="operador_sin_cobro",
                        telefono_bancario="",
                        version=F("version") + 1,
                    )
                    intento.estado = "rechazado"
                    _evento(comercio, pedido, intento, TipoEvento.COBRO_RECHAZADO)
                    return
                if any(len(valor) > 64 for valor in (qr_id, tx_id) if valor):
                    raise CommandError("Identificador demasiado largo.")
                if (
                    intento.canal == "qr_venta"
                    and (not qr_id or tx_id)
                    or intento.canal == "notificacion"
                    and (not tx_id or qr_id)
                ):
                    raise CommandError("Proporcione el identificador del canal.")
                cobro = Cobro(
                    comercio=comercio,
                    cuenta=cuenta,
                    canal=intento.canal,
                    monto=Decimal(intento.importe_efectivo_centavos) / 100,
                    concepto=intento.concepto,
                    vence_en=timezone.now() + timedelta(seconds=intento.expiracion_s),
                    pey_qr_id=qr_id,
                    pey_transaction_id=tx_id,
                    pey_bank_account_id=intento.pey_bank_account_id,
                )
                Cobro.objects.bulk_create([cobro])
                Movimiento.objects.create(
                    comercio=comercio,
                    cobro=cobro,
                    canal=intento.canal,
                    monto=cobro.monto,
                    concepto=cobro.concepto,
                    estado="pendiente",
                    origen="origen_pey",
                )
                IntentoCobro.objects.filter(pk=intento.pk).update(
                    estado="pendiente",
                    cobro=cobro,
                    telefono_bancario="",
                    error="operador_enlazo",
                    version=F("version") + 1,
                )
                intento.estado = "pendiente"
                intento.cobro = cobro
                _evento(comercio, pedido, intento, TipoEvento.COBRO_PENDIENTE)
                from pedidos.servicios.pagos import reaplicar_pendientes

                try:
                    with transaction.atomic():
                        reaplicar_pendientes(cobro)
                except Exception:
                    logger.warning(
                        "No se pudo reaplicar el aviso cobro_id=%s", cobro.pk
                    )
        except IntegrityError as exc:
            raise CommandError("El identificador ya está enlazado.") from exc
