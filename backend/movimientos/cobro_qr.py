"""Gate de alta de QR general (sin llamar a pey ni crear cobro en 5.2)."""

from ambito.cuenta import cuenta_esta_active
from ambito.exceptions import CuentaNoActiveError
from ambito.models import Comercio


def exigir_cuenta_active_para_alta_qr(comercio: Comercio) -> None:
    if not cuenta_esta_active(comercio):
        raise CuentaNoActiveError()


def preparar_alta_qr_general(comercio: Comercio) -> None:
    """Valida cuenta ACTIVE antes de dar de alta un QR general (épica QR)."""
    exigir_cuenta_active_para_alta_qr(comercio)
