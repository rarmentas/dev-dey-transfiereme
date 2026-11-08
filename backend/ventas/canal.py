"""Una sola venta viva por comercio: QR de venta o notificación, no el QR general."""

from django.db import connection
from django.db.models import Q
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


def vencer_pendientes(comercio: Comercio) -> None:
    """Marca vencidos los pendientes de venta con ``vence_en`` ya cumplido.

    Un ``vence_en`` nulo no vence: esa venta sigue viva. Corre fuera del
    ``atomic`` del alta para que un ``ErrorPey`` no deshaga el vencido.
    """
    ahora = timezone.now()
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


def venta_viva(comercio: Comercio) -> Movimiento | None:
    """Pendiente de venta que aún bloquea. ``vence_en`` nulo cuenta como vivo."""
    ahora = timezone.now()
    return (
        Movimiento.objects.select_related("cobro")
        .filter(
            comercio=comercio,
            canal__in=CANALES_VENTA,
            estado=Movimiento.Estado.PENDIENTE,
            cobro__isnull=False,
        )
        .filter(Q(cobro__vence_en__isnull=True) | Q(cobro__vence_en__gt=ahora))
        .order_by("pk")
        .first()
    )


def exigir_sin_venta_viva(comercio: Comercio) -> None:
    """Lanza ``VentaPendiente`` si el comercio ya tiene una venta vigente.

    Toma el candado del comercio. Fuera de ``transaction.atomic()`` falla:
    la 3.3 no puede olvidar el candado.
    """
    if not connection.in_atomic_block:
        raise RuntimeError(
            "exigir_sin_venta_viva debe correr dentro de transaction.atomic()."
        )
    bloquear_comercio(comercio)
    viva = venta_viva(comercio)
    if viva is not None:
        raise VentaPendiente(viva)
