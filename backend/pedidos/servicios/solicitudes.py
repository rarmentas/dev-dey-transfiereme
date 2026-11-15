"""Registro y corrección de solicitudes del canal."""

from django.db import transaction
from django.db.models import Max

from ambito.candados import bloquear_comercio
from pedidos.contratos.v1 import CodigoError, TipoEvento
from pedidos.errores import ErrorNucleo
from pedidos.models import Pedido
from pedidos.servicios.comandos import guardar, repeticion
from pedidos.servicios.cotizaciones import invalidar
from pedidos.servicios.eventos import emitir
from pedidos.servicios.intentos import exigir_editable


def registrar_solicitud(self, ctx, **datos):
    operacion = "registrar_solicitud"
    comercio, huella = self._preparar(operacion, ctx, datos, "mensaje_id")
    with transaction.atomic():
        comercio = bloquear_comercio(comercio)
        replay = repeticion(comercio, operacion, datos["command_key"], huella)
        if replay:
            return replay
        abierto = Pedido.objects.filter(
            comercio=comercio,
            instancia_id=ctx.instancia_id,
            sesion_id=ctx.sesion_id,
            conversacion_id=ctx.conversacion_id,
            abierto=True,
        ).first()
        if abierto:
            if abierto.cliente_externo_id != ctx.cliente_externo_id:
                raise ErrorNucleo(CodigoError.CONTEXTO_INVALIDO)
            raise ErrorNucleo(
                CodigoError.PEDIDO_ABIERTO,
                pedido_id=str(abierto.id),
                pedido_version=abierto.version,
            )
        numero = (
            Pedido.objects.filter(comercio=comercio).aggregate(n=Max("numero"))["n"]
            or 0
        ) + 1
        pedido = Pedido.objects.create(
            comercio=comercio,
            numero=numero,
            instancia_id=ctx.instancia_id,
            sesion_id=ctx.sesion_id,
            conversacion_id=ctx.conversacion_id,
            cliente_externo_id=ctx.cliente_externo_id,
            mensaje_origen_id=datos["mensaje_id"],
            message_key_origen=datos["message_key"],
            secuencia_conversacion_aplicada=datos["secuencia_conversacion"],
        )
        self._renglones(pedido, datos["renglones"])
        emitir(comercio, pedido, TipoEvento.PEDIDO_CREADO)
        return guardar(comercio, operacion, datos["command_key"], huella, pedido)


def corregir_borrador(self, ctx, **datos):
    operacion = "corregir_borrador"
    comercio, huella = self._preparar(operacion, ctx, datos, "mensaje_id")
    with transaction.atomic():
        comercio = bloquear_comercio(comercio)
        replay = repeticion(comercio, operacion, datos["command_key"], huella)
        if replay:
            return replay
        pedido = self._pedido(comercio, ctx, datos["pedido_id"], True)
        if (
            pedido.version != datos["expected_version"]
            or datos["secuencia_conversacion"] <= pedido.secuencia_conversacion_aplicada
        ):
            raise ErrorNucleo(CodigoError.VERSION_OBSOLETA)
        if pedido.estado == "cerrado":
            raise ErrorNucleo(CodigoError.PEDIDO_CONGELADO)
        exigir_editable(comercio, pedido)
        self._renglones(pedido, datos["renglones"])
        pedido.version += 1
        tenia_cotizacion = pedido.revision_vigente is not None
        invalidar(comercio, pedido)
        pedido.estado = "en_revision" if tenia_cotizacion else "borrador"
        pedido.secuencia_conversacion_aplicada = datos["secuencia_conversacion"]
        pedido.save()
        emitir(comercio, pedido, TipoEvento.PEDIDO_CORREGIDO)
        return guardar(comercio, operacion, datos["command_key"], huella, pedido)
