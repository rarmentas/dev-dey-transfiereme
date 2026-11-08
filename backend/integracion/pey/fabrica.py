from django.conf import settings

from integracion.pey.adaptador_desarrollo import AdaptadorDesarrolloPeyCuenta
from integracion.pey.adaptador_produccion import AdaptadorProduccionPeyCuenta
from integracion.pey.puerto import PuertoPeyCuenta


def obtener_adaptador_pey() -> PuertoPeyCuenta:
    modo = (getattr(settings, "PEY_ADAPTADOR", "") or "").strip().lower()
    if not modo:
        modo = "desarrollo" if settings.DEBUG else "produccion"
    if modo == "produccion":
        return AdaptadorProduccionPeyCuenta()
    return AdaptadorDesarrolloPeyCuenta()
