"""Registro en pey y serialización del estado de cuenta del comercio."""

from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from ambito.clabe import clabe_es_valida
from ambito.cuenta import cuenta_esta_active
from ambito.cuenta_sync import sincronizar_codi_status_con_detalle
from ambito.models import Comercio
from pey.cuentas import registrar_cuenta
from pey.seleccion import modo_adaptador
from pey.tipos import ErrorPey, ParametroInvalido

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
    clabe = (comercio.clabe or "").strip()
    tiene_clabe = clabe_es_valida(clabe)
    id_pey = (comercio.pey_bank_account_id or "").strip()
    tiene_id = bool(id_pey)
    puede_cobrar = cuenta_esta_active(comercio)

    if puede_cobrar:
        fase = "activa"
        paso = None
    elif not tiene_clabe:
        fase = "sin_clabe"
        paso = 1
    elif not tiene_id:
        fase = "pendiente_registro"
        paso = 2
    else:
        fase = "pendiente_activacion"
        paso = 3

    actualizado = comercio.pey_codi_status_actualizado_en
    actualizado_en = actualizado.isoformat() if actualizado else None

    return {
        "fase": fase,
        "paso": paso,
        "codi_status": comercio.pey_codi_status,
        "puede_cobrar": puede_cobrar,
        "clabe_enmascarada": enmascarar_clabe(clabe) if tiene_clabe else "",
        "tiene_cuenta_pey": tiene_id,
        "pey_bank_account_id_sufijo": sufijo_ulid(id_pey) if tiene_id else "",
        "actualizado_en": actualizado_en,
    }


def validar_registro_pey(*, nombre: str, entidad: str) -> tuple[str, str]:
    nombre_limpio = (nombre or "").strip()
    if not 1 <= len(nombre_limpio) <= 255:
        raise ParametroInvalido("Indique nombre de 1 a 255 caracteres.")
    entidad_limpia = (entidad or "").strip().upper()
    if entidad_limpia not in _ENTIDADES:
        raise ParametroInvalido("entidad debe ser BUSINESS o PERSON")
    return nombre_limpio, entidad_limpia


def registrar_cuenta_en_pey(
    comercio_id: int,
    *,
    nombre: str,
    entidad: str,
    alias: str = "",
    reemplazar: bool = False,
    transporte=None,
) -> tuple[Comercio, str]:
    """Registra la CLABE guardada en pey y persiste id/codiStatus."""
    exigir_modo_produccion()
    nombre_ok, entidad_ok = validar_registro_pey(nombre=nombre, entidad=entidad)
    alias_limpio = (alias or nombre_ok).strip()
    if not 1 <= len(alias_limpio) <= 255:
        raise ParametroInvalido("Indique alias de 1 a 255 caracteres.")

    with transaction.atomic():
        comercio = Comercio.objects.select_for_update().get(pk=comercio_id)
        clabe = (comercio.clabe or "").strip()
        if not clabe_es_valida(clabe):
            raise SinClabeGuardada()
        if (comercio.pey_bank_account_id or "").strip() and not reemplazar:
            raise CuentaPeyYaRegistrada()

        cuenta = registrar_cuenta(
            alias=alias_limpio,
            nombre=nombre_ok,
            clabe=clabe,
            entidad=entidad_ok,
            transporte=transporte,
        )
        if cuenta.codi_status == "ACTIVE":
            comercio.pey_codi_status = Comercio.PeyCodiStatus.ACTIVE
        else:
            comercio.pey_codi_status = Comercio.PeyCodiStatus.PENDING
        comercio.pey_bank_account_id = cuenta.id
        comercio.pey_codi_status_actualizado_en = timezone.now()
        comercio.save(
            update_fields=[
                "pey_bank_account_id",
                "pey_codi_status",
                "pey_codi_status_actualizado_en",
            ]
        )
        logger.info(
            "cuenta pey registrada comercio_id=%s codi_status=%s id_sufijo=%s",
            comercio.pk,
            comercio.pey_codi_status,
            sufijo_ulid(cuenta.id),
        )
        return comercio, cuenta.codi_status


def segundos_hasta_sync_permitido(comercio: Comercio) -> int | None:
    ts = comercio.pey_codi_status_actualizado_en
    if ts is None:
        return None
    delta = (timezone.now() - ts).total_seconds()
    if delta >= _INTERVALO_SYNC_S:
        return None
    restante = _INTERVALO_SYNC_S - delta
    return max(1, int(restante) + (1 if restante % 1 else 0))


def sincronizar_cuenta_y_estado(comercio: Comercio) -> tuple[dict, ErrorPey | None]:
    """Sincroniza con pey y devuelve el estado JSON y el error pey si hubo."""
    comercio, error = sincronizar_codi_status_con_detalle(comercio)
    comercio.refresh_from_db()
    return estado_cuenta_dict(comercio), error


def sincronizar_cuenta_y_estado_candado(
    comercio_id: int,
) -> tuple[dict, ErrorPey | None]:
    """Rate limit bajo candado; marca la ventana antes de llamar a pey."""
    with transaction.atomic():
        comercio = Comercio.objects.select_for_update().get(pk=comercio_id)
        restante = segundos_hasta_sync_permitido(comercio)
        if restante is not None:
            raise SyncMuyPronto(restante)
        comercio.pey_codi_status_actualizado_en = timezone.now()
        comercio.save(update_fields=["pey_codi_status_actualizado_en"])
    return sincronizar_cuenta_y_estado(comercio)


__all__ = [
    "AdaptadorNoProduccion",
    "CuentaPeyYaRegistrada",
    "SinClabeGuardada",
    "_MENSAJE_ADAPTADOR",
    "_MENSAJE_PEY_INCIERTO",
    "_MENSAJE_PEY_NO_REGISTRO",
    "_MENSAJE_SIN_CLABE",
    "_MENSAJE_SYNC_PRONTO",
    "_MENSAJE_YA_REGISTRADA",
    "enmascarar_clabe",
    "estado_cuenta_dict",
    "SyncMuyPronto",
    "registrar_cuenta_en_pey",
    "segundos_hasta_sync_permitido",
    "sincronizar_cuenta_y_estado",
    "sincronizar_cuenta_y_estado_candado",
    "validar_registro_pey",
]
