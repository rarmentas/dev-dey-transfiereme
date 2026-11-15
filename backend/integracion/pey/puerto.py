"""Contrato del puerto pey para consulta de cuenta."""

from dataclasses import dataclass
from typing import Protocol

from ambito.models import CuentaCobro

CODI_STATUS_PENDING = "pending"
CODI_STATUS_ACTIVE = "active"


@dataclass(frozen=True, slots=True)
class ResultadoCuenta:
    codi_status: str
    bank_account_id: str = ""


class PuertoPeyCuenta(Protocol):
    def consultar_cuenta(self, cuenta: CuentaCobro) -> ResultadoCuenta: ...
