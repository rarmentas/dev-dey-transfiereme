"""Eventos ordenados por comercio y cursores firmados."""

from django.core import signing

from pedidos.contratos.v1 import CodigoError, EventoDTO, TipoEvento
from pedidos.errores import ErrorNucleo
from pedidos.models import EventoPedido

SALT = "pedidos.cursor.v1"


def emitir(comercio, pedido, tipo, cotizacion=None, intento=None):
    comercio.secuencia_evento += 1
    comercio.save(update_fields=["secuencia_evento"])
    cot = (
        cotizacion
        or pedido.cotizaciones.filter(revision=pedido.revision_vigente).first()
    )
    ultimo = pedido.intentos.order_by("-creado_en", "-id").first()
    snapshot = {
        "estado": pedido.estado,
        "pedido_numero": pedido.numero,
        "pago_estado": ultimo.estado if ultimo else "sin_cobro",
        "preparacion": pedido.preparacion,
        "cotizacion_revision": cot.revision if cot else None,
        "total_comercial_centavos": cot.total_comercial_centavos if cot else None,
        "importe_efectivo_centavos": cot.importe_efectivo_centavos if cot else None,
        "demo_mode": cot.demo_mode if cot else None,
    }
    return EventoPedido.objects.create(
        comercio=comercio,
        pedido=pedido,
        secuencia_comercio=comercio.secuencia_evento,
        tipo=tipo.value,
        pedido_version=pedido.version,
        instancia_id=pedido.instancia_id,
        sesion_id=pedido.sesion_id,
        conversacion_id=pedido.conversacion_id,
        cotizacion=cot,
        intento=intento,
        snapshot=snapshot,
    )


def consultar(comercio, ctx, cursor, limite):
    secuencia = 0
    if cursor:
        try:
            valores = signing.loads(cursor, salt=SALT)
            if (
                not isinstance(valores, dict)
                or valores.get("v") != 1
                or valores.get("c") != str(comercio.pk)
                or valores.get("i") != ctx.instancia_id
                or valores.get("s") != ctx.sesion_id
                or type(valores.get("q")) is not int
                or valores["q"] < 0
            ):
                raise ValueError
            secuencia = valores["q"]
        except (signing.BadSignature, ValueError, TypeError):
            raise ErrorNucleo(CodigoError.CURSOR_INVALIDO) from None
    filas = list(
        EventoPedido.objects.filter(
            comercio=comercio, secuencia_comercio__gt=secuencia
        ).order_by("secuencia_comercio")[:500]
    )
    eventos = []
    for fila in filas:
        if fila.instancia_id == ctx.instancia_id and fila.sesion_id == ctx.sesion_id:
            if len(eventos) == limite:
                break
            eventos.append(
                EventoDTO(
                    str(fila.evento_id),
                    fila.secuencia_comercio,
                    TipoEvento(fila.tipo),
                    fila.creado_en,
                    str(fila.pedido_id),
                    fila.pedido_version,
                    fila.conversacion_id,
                    str(fila.cotizacion_id) if fila.cotizacion_id else None,
                    fila.snapshot,
                    str(fila.intento_id) if fila.intento_id else None,
                )
            )
        secuencia = fila.secuencia_comercio
    siguiente = signing.dumps(
        {
            "v": 1,
            "c": str(comercio.pk),
            "i": ctx.instancia_id,
            "s": ctx.sesion_id,
            "q": secuencia,
        },
        salt=SALT,
    )
    mas = EventoPedido.objects.filter(
        comercio=comercio, secuencia_comercio__gt=secuencia
    ).exists()
    return {"eventos": eventos, "next_cursor": siguiente, "has_more": mas}
