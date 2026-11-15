"""Elegibilidad de las cuentas de cobro."""

import re

from ambito.models import Comercio, CuentaCobro
from config.modo import destino_demo

_ULID = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")


def id_reservado_demo(ident: str) -> bool:
    """El destino demo, vigente o ya usado por un intento, no es de una cuenta."""
    from pedidos.models import IntentoCobro

    return bool(ident) and (
        ident == destino_demo()
        or IntentoCobro.objects.filter(
            demo_mode=True, pey_bank_account_id=ident
        ).exists()
    )


def cuenta_apta(cuenta: CuentaCobro | None) -> bool:
    return bool(
        cuenta and cuenta.registro_estado == "registrado"
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
