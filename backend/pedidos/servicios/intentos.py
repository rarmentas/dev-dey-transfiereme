"""Consultas y guardas de intentos."""

from ventas.canal import venta_viva

from pedidos.contratos.v1 import CodigoError
from pedidos.errores import ErrorNucleo
from pedidos.models import IntentoCobro

VIVOS = ("reservado", "enviando", "pendiente", "incierto")
CONGELAN = (*VIVOS, "vencido", "pagado")


def intento_de_pedido(pedido):
    return pedido.intentos.order_by("-creado_en", "-id").first()


def pago_estado_de(pedido):
    intento = intento_de_pedido(pedido)
    return intento.estado if intento else "sin_cobro"


def plaza_ocupada(comercio):
    return (
        IntentoCobro.objects.filter(comercio=comercio, estado__in=VIVOS).exists()
        or venta_viva(comercio) is not None
    )


def exigir_editable(comercio, pedido):
    intento = intento_de_pedido(pedido)
    if intento and intento.estado in CONGELAN:
        raise ErrorNucleo(CodigoError.PEDIDO_CONGELADO)
    if intento and intento.estado == "en_espera":
        from pedidos.servicios.cobros import descartar

        descartar(intento, "revision_editada")
        pedido.refresh_from_db()
