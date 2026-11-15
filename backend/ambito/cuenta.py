"""Elegibilidad de las cuentas de cobro."""

import re

from ambito.models import Comercio, CuentaCobro

_ULID = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")


def cuenta_apta(cuenta: CuentaCobro | None) -> bool:
    return bool(
        cuenta
        and cuenta.registro_estado == "registrado"
        and cuenta.codi_status == "active"
        and _ULID.fullmatch(cuenta.pey_bank_account_id)
    )


def cuenta_por_defecto(comercio: Comercio) -> CuentaCobro | None:
    if not comercio.cuenta_por_defecto_id:
        return None
    return CuentaCobro.objects.filter(
        pk=comercio.cuenta_por_defecto_id, comercio_id=comercio.pk
    ).first()


def cuenta_esta_active(comercio: Comercio) -> bool:
    return cuenta_apta(cuenta_por_defecto(comercio))
