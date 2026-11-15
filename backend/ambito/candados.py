"""Orden común de candados de comercio y cuenta."""

from ambito.models import Comercio, CuentaCobro


def bloquear_comercio(comercio: Comercio) -> Comercio:
    return Comercio.objects.select_for_update().get(pk=comercio.pk)


def bloquear_cuenta(cuenta: CuentaCobro) -> CuentaCobro:
    return CuentaCobro.objects.select_for_update().get(pk=cuenta.pk)
