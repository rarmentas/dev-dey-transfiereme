"""Cancelación idempotente de pedidos por el comercio."""

from django.db import transaction

from ambito.candados import bloquear_comercio
from movimientos.models import Movimiento
from pedidos.contratos.v1 import CodigoError, TipoEvento
from pedidos.contratos.validacion import hash_canonico
from pedidos.errores import ErrorNucleo
from pedidos.models import Pedido
from pedidos.servicios.cobros import descartar
from pedidos.servicios.comandos import guardar, repeticion
from pedidos.servicios.eventos import emitir


def cancelar(comercio, pedido_id, datos):
    operacion = "cancelar_pedido"
    huella = hash_canonico(
        operacion, {**datos, "pedido_id": str(pedido_id)}, str(comercio.pk)
    )
    with transaction.atomic():
        comercio = bloquear_comercio(comercio)
        replay = repeticion(comercio, operacion, datos["command_key"], huella)
        if replay:
            return replay
        pedido = (
            Pedido.objects.select_for_update()
            .filter(comercio=comercio, pk=pedido_id)
            .first()
        )
        if pedido is None:
            raise ErrorNucleo(CodigoError.PEDIDO_NO_ACCESIBLE)
        if pedido.version != datos["expected_version"]:
            raise ErrorNucleo(
                CodigoError.VERSION_OBSOLETA,
                pedido_id=str(pedido.pk),
                pedido_version=pedido.version,
            )
        if pedido.estado not in ("borrador", "en_revision", "cotizado", "aceptado"):
            raise ErrorNucleo(CodigoError.PEDIDO_CONGELADO)
        intentos = list(pedido.intentos.select_for_update().order_by("creado_en", "id"))
        if any(i.estado in ("enviando", "pendiente", "incierto") for i in intentos):
            raise ErrorNucleo(CodigoError.COBRO_EN_CURSO)
        if any(i.estado == "pagado" for i in intentos):
            raise ErrorNucleo(CodigoError.PEDIDO_CONGELADO)
        for intento in intentos:
            if intento.estado not in ("reservado", "en_espera"):
                continue
            if intento.cobro_id:
                for movimiento in Movimiento.objects.select_for_update().filter(
                    cobro_id=intento.cobro_id
                ):
                    if movimiento.estado == Movimiento.Estado.PENDIENTE:
                        movimiento.cambiar_estado(Movimiento.Estado.VENCIDO)
            if not descartar(
                intento, "pedido_cancelado", comercio=comercio, pedido=pedido
            ):
                raise ErrorNucleo(CodigoError.VERSION_OBSOLETA)
        pedido.estado = "cerrado"
        pedido.abierto = False
        pedido.version += 1
        pedido.save(update_fields=["estado", "abierto", "version", "actualizado_en"])
        emitir(comercio, pedido, TipoEvento.PEDIDO_CANCELADO)
        return guardar(comercio, operacion, datos["command_key"], huella, pedido)
