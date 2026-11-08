from integracion.pey.adaptador_desarrollo import AdaptadorDesarrolloPeyCuenta
from integracion.pey.adaptador_produccion import AdaptadorProduccionPeyCuenta
from integracion.pey.puerto import PuertoPeyCuenta
from pey.seleccion import modo_adaptador


def obtener_adaptador_pey() -> PuertoPeyCuenta:
    if modo_adaptador() == "desarrollo":
        return AdaptadorDesarrolloPeyCuenta()
    return AdaptadorProduccionPeyCuenta()
