"""Transiciones de preparación autorizadas por el tendero."""

from ambito.candados import bloquear_comercio
from django.db import transaction
from django.utils import timezone

from pedidos.contratos.v1 import CodigoError, TipoEvento
from pedidos.contratos.validacion import hash_canonico
from pedidos.errores import ErrorNucleo
from pedidos.models import Pedido
from pedidos.servicios.comandos import guardar, repeticion
from pedidos.servicios.eventos import emitir


def operar(comercio, pedido_id, datos, usuario, *, entregado=False):
    operacion = "marcar_entregado" if entregado else "marcar_listo"
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
        destino = "entregado" if entregado else "listo"
        if pedido.preparacion == destino:
            return guardar(comercio, operacion, datos["command_key"], huella, pedido)
        if pedido.version != datos["expected_version"]:
            raise ErrorNucleo(
                CodigoError.VERSION_OBSOLETA,
                pedido_id=str(pedido.id),
                pedido_version=pedido.version,
            )
        if entregado:
            if pedido.preparacion != "listo":
                raise ErrorNucleo(CodigoError.PREPARACION_INVALIDA)
            pedido.entregado_en = timezone.now()
            pedido.entregado_por = usuario
            pedido.estado = "cerrado"
            pedido.abierto = False
            evento = TipoEvento.PEDIDO_ENTREGADO
        else:
            ultimo = pedido.intentos.order_by("-creado_en", "-id").first()
            if not ultimo or ultimo.estado != "pagado":
                raise ErrorNucleo(CodigoError.PAGO_NO_CONFIRMADO)
            if pedido.preparacion != "pendiente":
                raise ErrorNucleo(CodigoError.PREPARACION_INVALIDA)
            pedido.listo_en = timezone.now()
            pedido.listo_por = usuario
            evento = TipoEvento.PEDIDO_LISTO
        pedido.preparacion = destino
        pedido.version += 1
        pedido.save()
        emitir(comercio, pedido, evento)
        return guardar(comercio, operacion, datos["command_key"], huella, pedido)
