"""Aceptación de cotizaciones vigentes."""

from django.db import transaction

from ambito.candados import bloquear_comercio
from config.modo import modo_de_comercio
from pedidos.contratos.v1 import CodigoError, TipoEvento
from pedidos.errores import ErrorNucleo
from pedidos.models import Aceptacion
from pedidos.servicios.comandos import guardar, repeticion
from pedidos.servicios.eventos import emitir


def aceptar_cotizacion(self, ctx, **datos):
    operacion = "aceptar_cotizacion"
    comercio, huella = self._preparar(
        operacion, ctx, datos, "mensaje_consentimiento_id"
    )
    with transaction.atomic():
        comercio = bloquear_comercio(comercio)
        replay = repeticion(comercio, operacion, datos["command_key"], huella)
        if replay:
            return replay
        pedido = self._pedido(comercio, ctx, datos["pedido_id"], True)
        cot = pedido.cotizaciones.filter(
            pk=datos["cotizacion_id"], revision=pedido.revision_vigente
        ).first()
        if (
            not cot
            or cot.revision != datos["cotizacion_revision"]
            or cot.token_resumen != datos["token_resumen"]
        ):
            raise ErrorNucleo(CodigoError.REVISION_OBSOLETA)
        if (
            (cot.demo_mode, cot.politica_cobro_version) != modo_de_comercio(comercio)
            or datos["politica_cobro_version"] != cot.politica_cobro_version
        ):
            raise ErrorNucleo(CodigoError.MODO_CAMBIO)
        if datos["importe_efectivo_mostrado_centavos"] != cot.importe_efectivo_centavos:
            raise ErrorNucleo(CodigoError.IMPORTE_NO_COINCIDE)
        msg = self.lector.leer_mensaje(ctx, datos["mensaje_consentimiento_id"])
        resumen = self.lector.leer_resumen(ctx, str(cot.id))
        if not resumen:
            leer_pendiente = getattr(self.lector, "leer_resumen_pendiente", None)
            pendiente = leer_pendiente(ctx, str(cot.id)) if leer_pendiente else None
            if (
                pendiente
                and pendiente.envio_iniciado_en
                and msg
                and msg.recibido_en >= pendiente.envio_iniciado_en
                and msg.tipo == "texto"
                and " ".join(msg.texto_normalizado.split()).casefold()
                == f"ACEPTAR {cot.token_resumen}".casefold()
                and pendiente.destinatario == ctx.cliente_externo_id
                and pendiente.token_resumen == cot.token_resumen
                and pendiente.cotizacion_revision == cot.revision
                and pendiente.total_comercial_centavos == cot.total_comercial_centavos
                and pendiente.importe_efectivo_centavos == cot.importe_efectivo_centavos
                and pendiente.demo_mode == cot.demo_mode
                and pendiente.politica_cobro_version == cot.politica_cobro_version
            ):
                raise ErrorNucleo(CodigoError.ACEPTACION_REQUERIDA, retryable=True)
        if (
            not msg
            or msg.mensaje_id != datos["mensaje_consentimiento_id"]
            or not msg.origen_autenticado
            or not isinstance(msg.texto_normalizado, str)
            or len(msg.texto_normalizado) > 4000
            or not resumen
            or resumen.estado != "enviado"
            or not resumen.id_proveedor
            or not resumen.enviado_en
            or not resumen.envio_iniciado_en
            or len(resumen.id_proveedor) > 200
            or resumen.destinatario != ctx.cliente_externo_id
            or resumen.cotizacion_id != str(cot.id)
            or resumen.token_resumen != cot.token_resumen
            or resumen.cotizacion_revision != cot.revision
            or resumen.total_comercial_centavos != cot.total_comercial_centavos
            or resumen.importe_efectivo_centavos != cot.importe_efectivo_centavos
            or resumen.demo_mode != cot.demo_mode
            or resumen.politica_cobro_version != cot.politica_cobro_version
            or msg.recibido_en < resumen.envio_iniciado_en
            or msg.tipo != "texto"
            or " ".join(msg.texto_normalizado.split()).casefold()
            != f"ACEPTAR {cot.token_resumen}".casefold()
        ):
            raise ErrorNucleo(
                CodigoError.ACEPTACION_REQUERIDA,
                retryable=bool(resumen and resumen.estado != "enviado"),
            )
        if Aceptacion.objects.filter(cotizacion=cot).exists():
            return guardar(
                comercio,
                operacion,
                datos["command_key"],
                huella,
                pedido,
                replayed=True,
            )
        if pedido.version != datos["expected_version"]:
            raise ErrorNucleo(CodigoError.VERSION_OBSOLETA)
        Aceptacion.objects.create(
            cotizacion=cot,
            pedido=pedido,
            comercio=comercio,
            instancia_id=ctx.instancia_id,
            sesion_id=ctx.sesion_id,
            conversacion_id=ctx.conversacion_id,
            cliente_externo_id=ctx.cliente_externo_id,
            mensaje_consentimiento_id=datos["mensaje_consentimiento_id"],
            salida_resumen_ref=resumen.id_proveedor,
            token_resumen=cot.token_resumen,
            importe_efectivo_centavos=cot.importe_efectivo_centavos,
            demo_mode=cot.demo_mode,
            politica_cobro_version=cot.politica_cobro_version,
        )
        pedido.estado = "aceptado"
        pedido.version += 1
        pedido.save()
        emitir(comercio, pedido, TipoEvento.PEDIDO_ACEPTADO, cot)
        return guardar(comercio, operacion, datos["command_key"], huella, pedido)
