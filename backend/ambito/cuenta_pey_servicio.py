"""Registro en pey y serialización del estado de cuenta del comercio."""

from __future__ import annotations

import logging

from ambito.clabe import clabe_es_valida
from ambito.cuenta import cuenta_esta_active
from ambito.models import Comercio
from pey.seleccion import modo_adaptador
from pey.tipos import ParametroInvalido

logger = logging.getLogger(__name__)

_INTERVALO_SYNC_S = 30
_ENTIDADES = frozenset({"BUSINESS", "PERSON"})

_MENSAJE_SIN_CLABE = "Indique una CLABE válida de 18 dígitos."
_MENSAJE_YA_REGISTRADA = (
    "El comercio ya tiene cuenta en pey. Envíe reemplazar: true para registrar otra."
)
_MENSAJE_ADAPTADOR = "El registro en pey no está disponible en este entorno."
_MENSAJE_PEY_NO_REGISTRO = "pey no registró la cuenta."
_MENSAJE_PEY_INCIERTO = "pey no respondió; el registro pudo haberse creado."
_MENSAJE_SYNC_PRONTO = "Espere antes de volver a sincronizar."


class SinClabeGuardada(Exception):
    """El comercio no tiene CLABE válida persistida."""


class CuentaPeyYaRegistrada(Exception):
    """Ya hay pey_bank_account_id y no se pidió reemplazar."""


class AdaptadorNoProduccion(Exception):
    """PEY_ADAPTADOR distinto de producción."""


class SyncMuyPronto(Exception):
    """Sincronización manual antes de la ventana de enfriamiento."""

    def __init__(self, reintento_en_segundos: int) -> None:
        self.reintento_en_segundos = reintento_en_segundos
        super().__init__(reintento_en_segundos)


def enmascarar_clabe(clabe: str) -> str:
    """14 asteriscos y los 4 últimos dígitos. Nunca la CLABE completa."""
    digitos = clabe or ""
    if len(digitos) <= 4:
        return "*" * len(digitos)
    return "*" * (len(digitos) - 4) + digitos[-4:]


def sufijo_ulid(identificador: str) -> str:
    limpio = (identificador or "").strip()
    if len(limpio) < 4:
        return ""
    return limpio[-4:]


def exigir_modo_produccion() -> None:
    try:
        modo = modo_adaptador()
    except Exception as exc:
        raise AdaptadorNoProduccion(str(exc)) from exc
    if modo != "produccion":
        raise AdaptadorNoProduccion("PEY_ADAPTADOR debe ser produccion.")


def estado_cuenta_dict(comercio: Comercio) -> dict:
    cuenta = (comercio.cuentas.filter(pk=comercio.cuenta_por_defecto_id).first()
              or comercio.cuentas.order_by("creada_en", "pk").first())
    clabe = cuenta.clabe if cuenta else ""
    ident = cuenta.pey_bank_account_id if cuenta else ""
    puede_cobrar = cuenta_esta_active(comercio)
    if puede_cobrar:
        fase, paso = "activa", None
    elif not clabe_es_valida(clabe):
        fase, paso = "sin_clabe", 1
    elif not ident:
        fase, paso = "pendiente_registro", 2
    else:
        fase, paso = "pendiente_activacion", 3
    actualizado = cuenta.sincronizada_en if cuenta else None
    return {"fase": fase, "paso": paso,
            "codi_status": cuenta.codi_status if cuenta else "pending",
            "puede_cobrar": puede_cobrar,
            "clabe_enmascarada": enmascarar_clabe(clabe) if clabe else "",
            "tiene_cuenta_pey": bool(ident),
            "pey_bank_account_id_sufijo": sufijo_ulid(ident),
            "actualizado_en": actualizado.isoformat() if actualizado else None}


def validar_registro_pey(*, nombre: str, entidad: str) -> tuple[str, str]:
    nombre_limpio = (nombre or "").strip()
    if not 1 <= len(nombre_limpio) <= 255:
        raise ParametroInvalido("Indique nombre de 1 a 255 caracteres.")
    entidad_limpia = (entidad or "").strip().upper()
    if entidad_limpia not in _ENTIDADES:
        raise ParametroInvalido("entidad debe ser BUSINESS o PERSON")
    return nombre_limpio, entidad_limpia
