from ambito.models import Comercio


def cuenta_esta_active(comercio: Comercio) -> bool:
    """El gate de cuenta ACTIVE solo acepta confirmación de pey.

    La marca local de la semilla de desarrollo no se consulta. Hoy no
    hay estado de pey persistido, así que nadie pasa el gate por sembrarse.
    """
    del comercio
    return False
