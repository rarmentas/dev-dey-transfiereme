"""Candados en orden común para pagos."""

from ambito.models import Comercio, CuentaCobro
from movimientos.models import Cobro, Movimiento

from pedidos.models import IntentoCobro, Pedido


def bloquear_para_pago(
    comercio_id,
    pedido_id=None,
    intento_id=None,
    cuenta_id=None,
    cobro_id=None,
    movimiento_id=None,
):
    comercio = Comercio.objects.select_for_update().get(pk=comercio_id)
    objetos = [comercio]
    for modelo, pk in (
        (Pedido, pedido_id),
        (IntentoCobro, intento_id),
        (CuentaCobro, cuenta_id),
        (Cobro, cobro_id),
        (Movimiento, movimiento_id),
    ):
        objetos.append(modelo.objects.select_for_update().get(pk=pk) if pk else None)
    return tuple(objetos)
