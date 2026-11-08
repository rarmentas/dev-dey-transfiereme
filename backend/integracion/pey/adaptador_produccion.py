"""Adaptador de producción: no usa banderas locales de semilla (implementación HTTP en 5.4)."""

from ambito.models import Comercio

from integracion.pey.puerto import CODI_STATUS_PENDING, ResultadoCuenta


class AdaptadorProduccionPeyCuenta:
    """En 5.2 devuelve PENDING hasta integrar consulta real contra pey."""

    def consultar_cuenta_por_clabe(self, comercio: Comercio) -> ResultadoCuenta:
        del comercio
        return ResultadoCuenta(codi_status=CODI_STATUS_PENDING)
