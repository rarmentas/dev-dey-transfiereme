"""Construcción de avisos a partir del feed del núcleo."""

from django.db import transaction

from canales import mensajes
from canales.conversacion import contexto
from canales.models import ConversacionCanal, CursorCanal, SesionCanal
from canales.salidas import preparar
from pedidos.contratos.v1 import CONTRATO_VERSION, ContextoConsumidorV1, TipoEvento


def procesar_avisos(nucleo, lector):
    for sesion in SesionCanal.objects.filter(estado="activa"):
        cursor, _ = CursorCanal.objects.get_or_create(
            consumidor="avisos", sesion=sesion
        )
        ctx = ContextoConsumidorV1(sesion.instancia_id, sesion.sesion_id)
        respuesta = nucleo.consultar_eventos(
            ctx,
            contrato_version=CONTRATO_VERSION,
            cursor=cursor.cursor or None,
            limite=50,
        )
        if not respuesta.ok:
            continue
        pendientes = []
        for evento in respuesta.data["eventos"]:
            plantillas = {
                TipoEvento.PAGO_CONFIRMADO: mensajes.PAGADO,
                TipoEvento.PEDIDO_LISTO: mensajes.LISTO,
                TipoEvento.PEDIDO_ENTREGADO: mensajes.ENTREGADO,
                TipoEvento.COBRO_INCIERTO: mensajes.COBRO_INCIERTO,
                TipoEvento.COBRO_RECHAZADO: mensajes.COBRO_RECHAZADO,
                TipoEvento.COBRO_VENCIDO: mensajes.COBRO_VENCIDO,
                TipoEvento.COBRO_DESCARTADO: mensajes.COBRO_DESCARTADO,
            }
            if (
                evento.tipo != TipoEvento.COTIZACION_PUBLICADA
                and evento.tipo not in plantillas
            ):
                continue
            conversacion = ConversacionCanal.objects.filter(
                sesion=sesion, pk=evento.conversacion_id
            ).first()
            if not conversacion:
                continue
            if evento.tipo in plantillas:
                snapshot = evento.snapshot
                numero = snapshot.get("pedido_numero")
                texto = plantillas[evento.tipo].format(
                    pedido_numero=numero if numero is not None else ""
                )
                importe = snapshot.get("importe_efectivo_centavos")
                total = snapshot.get("total_comercial_centavos")
                if importe is not None:
                    texto += f" Importe: ${importe / 100:.2f}."
                if snapshot.get("demo_mode") and total is not None:
                    texto += f" Total comercial: ${total / 100:.2f}."
                if nucleo.ES_SIMULACION:
                    texto = "[SIMULACIÓN] " + texto
                pendientes.append((conversacion, evento, {"texto": texto}, "aviso"))
                continue
            consulta = nucleo.consultar_pedido(
                contexto(conversacion),
                contrato_version=CONTRATO_VERSION,
                pedido_id=evento.pedido_id,
            )
            if not consulta.ok:
                if consulta.error.retryable:
                    pendientes = None
                    break
                continue
            pedido = consulta.data["pedido"]
            cot = pedido.cotizacion
            if not cot or cot.id != evento.cotizacion_id:
                continue
            lineas = [
                f"{r['descripcion']}: {r['cantidad']} {r.get('unidad', '')}"
                f" — ${r['subtotal_centavos'] / 100:.2f}"
                for r in cot.renglones
            ]
            lineas.append(f"Total: ${cot.total_comercial_centavos / 100:.2f}")
            if cot.demo_mode:
                lineas.append(
                    f"Importe efectivo: ${cot.importe_efectivo_centavos / 100:.2f}"
                )
            lineas.append(f"Para aceptar escribe ACEPTAR {cot.token_resumen}")
            texto = "\n".join(lineas)
            if nucleo.ES_SIMULACION:
                texto = "[SIMULACIÓN] " + texto
            payload = {
                "texto": texto,
                "cotizacion_id": cot.id,
                "cotizacion_revision": cot.revision,
                "token_resumen": cot.token_resumen,
                "total_comercial_centavos": cot.total_comercial_centavos,
                "importe_efectivo_centavos": cot.importe_efectivo_centavos,
                "demo_mode": cot.demo_mode,
                "politica_cobro_version": cot.politica_cobro_version,
                "pedido_id": pedido.id,
                "pedido_version": pedido.version,
            }
            pendientes.append((conversacion, evento, payload, "cotizacion_resumen"))
        if pendientes is None:
            continue
        with transaction.atomic():
            bloqueado = CursorCanal.objects.select_for_update().get(pk=cursor.pk)
            if bloqueado.cursor != cursor.cursor:
                continue
            for conversacion, evento, payload, tipo in pendientes:
                preparar(
                    conversacion,
                    f"evento:{evento.evento_id}",
                    tipo,
                    payload,
                )
            bloqueado.cursor = respuesta.data["next_cursor"]
            bloqueado.save(update_fields=["cursor", "actualizado_en"])
