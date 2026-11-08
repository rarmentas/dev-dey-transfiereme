"""Adaptador local. No habla con pey ni lee sus secretos."""

import secrets
import uuid
from decimal import Decimal

from ambito.models import Comercio

from pey.tipos import ErrorPey, NotificacionCreada, ParametroInvalido, QrCreado
from pey.validacion import validar_monto_pago, validar_notificacion, validar_qr

_TIPO_AVISO_QR_PAGADO = "codi.qr.payment_received"
_LARGO_TRANSACTION_ID = 64


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
            transaction_id=self.nuevo_transaction_id(),
            codi_id=f"{secrets.randbelow(10**20):020d}",
        )

    def nuevo_transaction_id(self) -> str:
        return f"dev-tx-{uuid.uuid4().hex}"

    def cuerpo_aviso_qr_pagado(
        self,
        *,
        monto: Decimal,
        codi_qr_id: str,
        transaction_id: str | None = None,
        concepto: str = "",
    ) -> dict[str, object]:
        """Plantilla de aviso QR pagado, compatible con el lector del webhook."""
        monto_ok = validar_monto_pago(monto)
        if not isinstance(codi_qr_id, str) or not codi_qr_id.strip():
            raise ParametroInvalido("codi_qr_id debe ser texto no vacío")
        if transaction_id is None:
            transaction_id = self.nuevo_transaction_id()
        elif (
            not isinstance(transaction_id, str)
            or not transaction_id.strip()
            or len(transaction_id) > _LARGO_TRANSACTION_ID
        ):
            raise ParametroInvalido("transaction_id no es usable")
        return {
            "type": _TIPO_AVISO_QR_PAGADO,
            "amount": monto_ok,
            "transactionId": transaction_id,
            "codiQrId": codi_qr_id,
            "concept": concepto or "Transferencia",
        }

    def cuenta_active(self, comercio: Comercio) -> bool:
        return bool(comercio.semilla_active_dev)

    def _exigir_exito(self) -> None:
        if self._fallar_con is not None:
            raise self._fallar_con
