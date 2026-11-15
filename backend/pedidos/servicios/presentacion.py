"""Conversión de modelos a DTO del contrato."""

from datetime import datetime
from decimal import Decimal

from ambito.cuenta_pey_servicio import enmascarar_clabe
from pedidos.contratos.calculo import subtotal_centavos
from pedidos.contratos.v1 import (
    AceptacionDTO,
    CotizacionDTO,
    CobroDTO,
    CanalCobro,
    EstadoPago,
    EstadoPedido,
    EstadoPreparacion,
    PedidoDTO,
    RenglonDTO,
    Resolucion,
)
from pedidos.contratos.validacion import ErrorContrato


def cotizacion_dto(cot):
    if cot is None:
        return None
    return CotizacionDTO(
        str(cot.id),
        cot.revision,
        cot.snapshot,
        cot.total_comercial_centavos,
        cot.importe_efectivo_centavos,
        cot.moneda,
        cot.demo_mode,
        cot.politica_cobro_version,
        cot.token_resumen,
        cot.publicada_en,
    )


def pedido_dto(pedido):
    cot = pedido.cotizaciones.filter(revision=pedido.revision_vigente).first()
    aceptacion = getattr(cot, "aceptacion", None) if cot else None
    numero = pedido.cliente_externo_id.split("@", 1)[0]
    etiqueta = "".join(c for c in numero if c.isdigit())[-4:]
    renglones = []
    for r in pedido.renglones.order_by("posicion"):
        subtotal = None
        if r.resolucion == "incluido":
            try:
                subtotal = subtotal_centavos(r.cantidad, r.precio_unitario_centavos)
            except ErrorContrato:
                subtotal = 0
        renglones.append(
            RenglonDTO(
                str(r.id),
                r.posicion,
                r.texto_solicitado,
                r.cantidad_solicitada,
                r.unidad_solicitada,
                r.descripcion,
                r.cantidad,
                r.unidad,
                r.precio_unitario_centavos,
                subtotal,
                Resolucion(r.resolucion),
                r.motivo_exclusion,
            )
        )
    aceptado = (
        AceptacionDTO(
            str(aceptacion.id),
            str(cot.id),
            aceptacion.aceptada_en,
            {"conversacion_id": pedido.conversacion_id, "cliente_etiqueta": etiqueta},
        )
        if aceptacion and pedido.estado == "aceptado"
        else None
    )
    ultimo = pedido.intentos.select_related("cuenta", "cobro").order_by(
        "-creado_en", "-id"
    ).first()
    cobro = ultimo.cobro if ultimo else None
    intento_dto = CobroDTO(
        str(ultimo.pk), str(cobro.pk) if cobro else None,
        CanalCobro(ultimo.canal), EstadoPago(ultimo.estado),
        cobro.qr_string or None if cobro else None,
        cobro.vence_en if cobro else None,
        enmascarar_clabe(ultimo.cuenta.clabe) if ultimo.cuenta_id else None,
        str(ultimo.aceptacion_id) if ultimo.aceptacion_id else None,
    ) if ultimo else None
    return PedidoDTO(
        str(pedido.id),
        pedido.numero,
        pedido.version,
        EstadoPedido(pedido.estado),
        pedido.abierto,
        {
            "canal": "whatsapp",
            "mensaje_id": str(pedido.mensaje_origen_id),
            "creado_en": pedido.creado_en,
        },
        etiqueta,
        renglones,
        cotizacion_dto(cot),
        pedido.ultima_revision,
        aceptado,
        EstadoPago(ultimo.estado) if ultimo else EstadoPago.SIN_COBRO,
        EstadoPreparacion(pedido.preparacion),
        intento_dto,
        False,
    )


def pedido_desde_json(data):
    data = dict(data)
    data["estado"] = EstadoPedido(data["estado"])
    data["pago_estado"] = EstadoPago(data["pago_estado"])
    data["preparacion"] = EstadoPreparacion(data["preparacion"])
    data["origen"]["creado_en"] = datetime.fromisoformat(
        data["origen"]["creado_en"].replace("Z", "+00:00")
    )
    filas = []
    for item in data["renglones"]:
        item = dict(item)
        for campo in ("cantidad", "cantidad_solicitada"):
            if item[campo] is not None:
                item[campo] = Decimal(item[campo])
        item["resolucion"] = Resolucion(item["resolucion"])
        filas.append(RenglonDTO(**item))
    data["renglones"] = filas
    if data["cotizacion"]:
        cot = dict(data["cotizacion"])
        cot["publicada_en"] = datetime.fromisoformat(
            cot["publicada_en"].replace("Z", "+00:00")
        )
        data["cotizacion"] = CotizacionDTO(**cot)
    if data["aceptacion"]:
        aceptacion = dict(data["aceptacion"])
        aceptacion["aceptada_en"] = datetime.fromisoformat(
            aceptacion["aceptada_en"].replace("Z", "+00:00")
        )
        data["aceptacion"] = AceptacionDTO(**aceptacion)
    if data["intento"]:
        intento = dict(data["intento"])
        intento["canal"] = CanalCobro(intento["canal"])
        intento["estado"] = EstadoPago(intento["estado"])
        if intento["vencimiento"]:
            intento["vencimiento"] = datetime.fromisoformat(
                intento["vencimiento"].replace("Z", "+00:00")
            )
        data["intento"] = CobroDTO(**intento)
    return PedidoDTO(**data)
