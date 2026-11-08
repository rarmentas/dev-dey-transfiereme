"""Contrato del puerto pey para consulta de cuenta (sin cobro)."""

from dataclasses import dataclass
from typing import Protocol

from ambito.models import Comercio

CODI_STATUS_PENDING = "pending"
CODI_STATUS_ACTIVE = "active"


@dataclass(frozen=True, slots=True)
class ResultadoCuenta:
    codi_status: str
    bank_account_id: str = ""


class PuertoPeyCuenta(Protocol):
    def consultar_cuenta_por_clabe(self, comercio: Comercio) -> ResultadoCuenta: ...
