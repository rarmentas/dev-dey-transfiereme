"""Adaptador local. No habla con pey ni lee sus secretos."""

import secrets
import uuid
from decimal import Decimal

from ambito.models import Comercio

from pey.tipos import ErrorPey, NotificacionCreada, QrCreado
from pey.validacion import validar_notificacion, validar_qr


class AdaptadorDesarrollo:
    def __init__(self, fallar_con: ErrorPey | None = None) -> None:
        self._fallar_con = fallar_con

    def crear_qr(
        self,
        *,
        monto: Decimal,
        concepto: str = "",
        expiracion_s: int = 0,
        num_ref: str = "0",
    ) -> QrCreado:
        validar_qr(
            monto=monto,
            concepto=concepto,
            expiracion_s=expiracion_s,
            num_ref=num_ref,
        )
        self._exigir_exito()
        identificador = f"dev-qr-{uuid.uuid4().hex}"
        return QrCreado(id=identificador, qr_string=f"cody-dev://qr/{identificador}")

    def crear_notificacion(
        self,
        *,
        monto: Decimal,
        telefono: str,
        concepto: str = "",
        expiracion_s: int = 360,
        num_ref: str = "0",
    ) -> NotificacionCreada:
        validar_notificacion(
            monto=monto,
            telefono=telefono,
            concepto=concepto,
            expiracion_s=expiracion_s,
            num_ref=num_ref,
        )
        self._exigir_exito()
        return NotificacionCreada(
            transaction_id=f"dev-tx-{uuid.uuid4().hex}",
            codi_id=f"{secrets.randbelow(10**20):020d}",
        )

    def cuenta_active(self, comercio: Comercio) -> bool:
        return bool(comercio.semilla_active_dev)

    def _exigir_exito(self) -> None:
        if self._fallar_con is not None:
            raise self._fallar_con
