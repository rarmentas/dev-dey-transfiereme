"""Consulta de cuenta en producción."""

from ambito.models import CuentaCobro
from integracion.pey.puerto import (
    CODI_STATUS_ACTIVE,
    CODI_STATUS_PENDING,
    ResultadoCuenta,
)
from pey.cuentas import consultar_cuenta


class AdaptadorProduccionPeyCuenta:
    def consultar_cuenta(self, cuenta: CuentaCobro) -> ResultadoCuenta:
        if not cuenta.pey_bank_account_id:
            return ResultadoCuenta(codi_status=CODI_STATUS_PENDING)
        remota = consultar_cuenta(cuenta.pey_bank_account_id)
        activo = remota.codi_status == "ACTIVE" and remota.clabe == cuenta.clabe
        return ResultadoCuenta(
            codi_status=CODI_STATUS_ACTIVE if activo else CODI_STATUS_PENDING,
            bank_account_id=cuenta.pey_bank_account_id,
        )
