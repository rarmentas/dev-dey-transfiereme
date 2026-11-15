"""Publicación e invalidación de cotizaciones."""

from config.modo import modo_de_comercio
from pedidos.contratos.calculo import (
    importe_efectivo,
    subtotal_centavos,
    total_centavos,
)
from pedidos.contratos.v1 import CodigoError, TipoEvento
from pedidos.errores import ErrorNucleo
from pedidos.models import Cotizacion
from pedidos.servicios.eventos import emitir


def invalidar(comercio, pedido):
    cot = pedido.cotizaciones.filter(revision=pedido.revision_vigente).first()
    if cot:
        pedido.revision_vigente = None
        pedido.estado = "en_revision"
        emitir(comercio, pedido, TipoEvento.COTIZACION_INVALIDADA, cot)


def publicar(comercio, pedido, usuario=None):
    renglones = list(pedido.renglones.order_by("posicion"))
    pendientes = [str(r.id) for r in renglones if r.resolucion == "pendiente"]
    incluidos = [r for r in renglones if r.resolucion == "incluido"]
    if pendientes or not incluidos:
        exc = ErrorNucleo(CodigoError.RENGLON_PENDIENTE)
        exc.errores = {"renglones_pendientes": pendientes}
        raise exc
    snapshot = []
    for r in incluidos:
        subtotal = subtotal_centavos(r.cantidad, r.precio_unitario_centavos)
        snapshot.append(
            {
                "renglon_id": str(r.id),
                "descripcion": r.descripcion,
                "cantidad": str(r.cantidad),
                "unidad": r.unidad,
                "precio_unitario_centavos": r.precio_unitario_centavos,
                "subtotal_centavos": subtotal,
            }
        )
    total = total_centavos([r["subtotal_centavos"] for r in snapshot])
    pedido.version += 1
    invalidar(comercio, pedido)
    revision = pedido.ultima_revision + 1
    modo = modo_de_comercio(comercio)
    cot = Cotizacion.objects.create(
        comercio=comercio,
        pedido=pedido,
        revision=revision,
        pedido_version_publicada=pedido.version,
        snapshot=snapshot,
        total_comercial_centavos=total,
        importe_efectivo_centavos=importe_efectivo(total, modo.demo),
        demo_mode=modo.demo,
        politica_cobro_version=modo.politica,
        token_resumen=f"P{pedido.numero}-R{revision}",
        publicada_por=usuario,
    )
    pedido.revision_vigente = revision
    pedido.ultima_revision = revision
    pedido.estado = "cotizado"
    pedido.save()
    emitir(comercio, pedido, TipoEvento.COTIZACION_PUBLICADA, cot)
    return pedido
