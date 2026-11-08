"""Puerto que van a usar QR, venta, notificación y estado de cuenta."""

from decimal import Decimal
from typing import Protocol

from ambito.models import Comercio

from pey.tipos import NotificacionCreada, QrCreado


class PuertoPey(Protocol):
    def crear_qr(
        self,
        *,
        monto: Decimal,
        concepto: str = "",
        expiracion_s: int = 0,
        num_ref: str = "0",
    ) -> QrCreado: ...

    def crear_notificacion(
        self,
        *,
        monto: Decimal,
        telefono: str,
        concepto: str = "",
        expiracion_s: int = 360,
        num_ref: str = "0",
    ) -> NotificacionCreada: ...

    def cuenta_active(self, comercio: Comercio) -> bool: ...
