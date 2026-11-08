from ambito.models import Comercio


def cuenta_esta_active(comercio: Comercio) -> bool:
    """El gate de cuenta ACTIVE solo acepta el codiStatus persistido desde pey."""
    return comercio.pey_codi_status == Comercio.PeyCodiStatus.ACTIVE
