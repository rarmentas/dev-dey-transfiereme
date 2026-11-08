"""Una sola venta viva por comercio: QR de venta o notificación, no el QR general."""

from django.utils import timezone

from ambito.models import Comercio
from movimientos.exceptions import TransicionInvalida
from movimientos.models import Movimiento

CANALES_VENTA = (
    Movimiento.Canal.QR_VENTA,
    Movimiento.Canal.NOTIFICACION,
)


class VentaPendiente(Exception):
    """Ya hay un QR de venta o una notificación pendiente y vigente."""

    def __init__(self, movimiento: Movimiento) -> None:
        self.movimiento = movimiento
        super().__init__("Ya hay una venta pendiente.")


def bloquear_comercio(comercio: Comercio) -> Comercio:
    """Bloquea la fila del comercio. Hay que llamarlo dentro de ``atomic()``."""
    return Comercio.objects.select_for_update().get(pk=comercio.pk)


def venta_viva(comercio: Comercio) -> Movimiento | None:
    """Pendiente de venta con vencimiento futuro. Antes marca los ya vencidos."""
    ahora = timezone.now()
    _vencer_pendientes(comercio, ahora)
    return (
        Movimiento.objects.select_related("cobro")
        .filter(
            comercio=comercio,
            canal__in=CANALES_VENTA,
            estado=Movimiento.Estado.PENDIENTE,
            cobro__vence_en__gt=ahora,
        )
        .order_by("pk")
        .first()
    )


def exigir_sin_venta_viva(comercio: Comercio) -> None:
    """Lanza ``VentaPendiente`` si el comercio ya tiene una venta vigente."""
    viva = venta_viva(comercio)
    if viva is not None:
        raise VentaPendiente(viva)


def _vencer_pendientes(comercio: Comercio, ahora) -> None:
    pendientes = Movimiento.objects.select_related("cobro").filter(
        comercio=comercio,
        canal__in=CANALES_VENTA,
        estado=Movimiento.Estado.PENDIENTE,
        cobro__vence_en__lte=ahora,
    )
    for movimiento in pendientes:
        try:
            movimiento.cambiar_estado(Movimiento.Estado.VENCIDO)
        except TransicionInvalida:
            pass
