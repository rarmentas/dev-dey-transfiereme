"""Adaptador local: simula codiStatus sin red ni credenciales de pey."""

from ambito.clabe import clabe_es_valida
from ambito.models import Comercio

from integracion.pey.puerto import (
    CODI_STATUS_ACTIVE,
    CODI_STATUS_PENDING,
    ResultadoCuenta,
)


def _bank_account_id_simulado(comercio: Comercio) -> str:
    return f"01DEVSIM{comercio.pk:018d}"[:26]


class AdaptadorDesarrolloPeyCuenta:
    """ACTIVE simulado solo con CLABE válida y marca de semilla de desarrollo."""

    def consultar_cuenta_por_clabe(self, comercio: Comercio) -> ResultadoCuenta:
        if not clabe_es_valida(comercio.clabe):
            return ResultadoCuenta(codi_status=CODI_STATUS_PENDING)
        if comercio.semilla_active_dev:
            return ResultadoCuenta(
                codi_status=CODI_STATUS_ACTIVE,
                bank_account_id=_bank_account_id_simulado(comercio),
            )
        return ResultadoCuenta(codi_status=CODI_STATUS_PENDING)
