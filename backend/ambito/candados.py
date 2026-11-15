"""Orden común de candados de comercio y cuenta."""

from django.db.models import Q

from ambito.models import Comercio, CuentaCobro


def bloquear_comercio(comercio: Comercio) -> Comercio:
    return Comercio.objects.select_for_update().get(pk=comercio.pk)


def bloquear_comercio_y_demo(comercio: Comercio) -> Comercio:
    """Bloquea el comercio y el demo en orden de pk; el demo reserva su destino."""
    filas = (
        Comercio.objects.select_for_update()
        .filter(Q(pk=comercio.pk) | Q(es_demo=True))
        .order_by("pk")
    )
    return next(fila for fila in filas if fila.pk == comercio.pk)


def bloquear_cuenta(cuenta: CuentaCobro) -> CuentaCobro:
    return CuentaCobro.objects.select_for_update().get(pk=cuenta.pk)
