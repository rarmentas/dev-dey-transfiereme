"""Adaptador de producción: consulta la cuenta ya registrada. No usa la semilla."""

import logging

from ambito.models import Comercio
from pey.cuentas import consultar_cuenta

from integracion.pey.puerto import CODI_STATUS_ACTIVE, CODI_STATUS_PENDING, ResultadoCuenta

logger = logging.getLogger(__name__)


class AdaptadorProduccionPeyCuenta:
    """PENDING si la cuenta no está registrada. ACTIVE solo si pey lo dice y la CLABE coincide."""

    def consultar_cuenta_por_clabe(self, comercio: Comercio) -> ResultadoCuenta:
        identificador = (comercio.pey_bank_account_id or "").strip()
        if not identificador:
            return ResultadoCuenta(codi_status=CODI_STATUS_PENDING)
        cuenta = consultar_cuenta(identificador)
        if cuenta.codi_status == "ACTIVE" and cuenta.clabe == (comercio.clabe or ""):
            return ResultadoCuenta(
                codi_status=CODI_STATUS_ACTIVE,
                bank_account_id=identificador,
            )
        if cuenta.codi_status == "ACTIVE":
            logger.warning(
                "cuenta pey no coincide con la CLABE comercio_id=%s clabe_final=%s",
                comercio.pk,
                (cuenta.clabe or "")[-4:],
            )
        return ResultadoCuenta(
            codi_status=CODI_STATUS_PENDING,
            bank_account_id=identificador,
        )
