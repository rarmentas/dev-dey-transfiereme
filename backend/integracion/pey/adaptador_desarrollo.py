"""Consulta de cuenta simulada."""

from ambito.clabe import clabe_es_valida
from ambito.models import CuentaCobro
from integracion.pey.puerto import (
    CODI_STATUS_ACTIVE,
    CODI_STATUS_PENDING,
    ResultadoCuenta,
)


class AdaptadorDesarrolloPeyCuenta:
    def consultar_cuenta(self, cuenta: CuentaCobro) -> ResultadoCuenta:
        if clabe_es_valida(cuenta.clabe) and cuenta.comercio.semilla_active_dev:
            return ResultadoCuenta(
                codi_status=CODI_STATUS_ACTIVE,
                bank_account_id=("01DEVS1M" + cuenta.pk.hex.upper())[:26],
            )
        return ResultadoCuenta(codi_status=CODI_STATUS_PENDING)
