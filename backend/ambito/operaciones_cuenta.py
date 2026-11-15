"""Operaciones durables de registro y sincronización de cuentas."""

import hashlib
import json
import re
import uuid
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from ambito.candados import (
    bloquear_comercio,
    bloquear_comercio_y_demo,
    bloquear_cuenta,
)
from ambito.cuenta import id_reservado_demo
from ambito.cuenta_pey_servicio import exigir_modo_produccion, validar_registro_pey
from ambito.models import CuentaCobro, OperacionCuenta
from pey.cuentas import consultar_cuenta, registrar_cuenta
from pey.tipos import ErrorPey, ParametroInvalido

_ULID = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")


class ErrorOperacion(Exception):
    def __init__(self, codigo: str, status: int = 409, **datos):
        self.codigo, self.status, self.datos = codigo, status, datos
        super().__init__(codigo)


def _error_seguro(error: ErrorPey) -> str:
    tipo = re.sub(r"[^A-Z0-9_]", "", error.tipo.upper())[:80]
    request_id = re.sub(r"[^A-Za-z0-9_-]", "", error.request_id or "")[:64]
    return f"{tipo} {request_id}".strip()


def registrar(
    cuenta: CuentaCobro,
    *,
    nombre: str,
    entidad: str,
    alias: str,
    clave: str,
    version: int,
    transporte=None,
):
    try:
        nombre, entidad = validar_registro_pey(nombre=nombre, entidad=entidad)
        alias = (alias or nombre).strip()
        if not 1 <= len(alias) <= 255 or not isinstance(clave, str):
            raise ParametroInvalido()
        if not 1 <= len(clave) <= 128 or type(version) is not int:
            raise ParametroInvalido()
    except (ParametroInvalido, AttributeError, TypeError):
        raise ErrorOperacion("PAYLOAD_INVALIDO", 400) from None
    payload = {"nombre": nombre, "entidad": entidad, "alias": alias}
    huella = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    exigir_modo_produccion()
    with transaction.atomic():
        bloquear_comercio(cuenta.comercio)
        cuenta = bloquear_cuenta(cuenta)
        previa = cuenta.operaciones.filter(clave=clave).first()
        if previa:
            if previa.hash_payload != huella:
                raise ErrorOperacion("CLAVE_REUTILIZADA")
            if previa.estado == "incierta" or previa.estado in (
                "pendiente",
                "en_curso",
            ):
                raise ErrorOperacion("REGISTRO_INCIERTO")
            if previa.estado == "fallida":
                raise ErrorOperacion("PEY_RECHAZO", 502)
            if previa.estado == "descartada":
                raise ErrorOperacion("VERSION_OBSOLETA")
            return cuenta, True
        if cuenta.version != version:
            raise ErrorOperacion("VERSION_OBSOLETA")
        if cuenta.registro_estado in ("incierto", "registrando"):
            raise ErrorOperacion("REGISTRO_INCIERTO")
        if cuenta.registro_estado == "registrado":
            raise ErrorOperacion("CUENTA_YA_REGISTRADA")
        cuenta.version += 1
        cuenta.registro_estado = "registrando"
        cuenta.save(update_fields=["version", "registro_estado"])
        op = OperacionCuenta.objects.create(
            cuenta=cuenta,
            tipo="registro",
            origen="ui",
            estado="en_curso",
            clave=clave,
            hash_payload=huella,
            payload=payload,
            version_reclamada=cuenta.version,
            lease_token=uuid.uuid4(),
            lease_hasta=timezone.now() + timedelta(minutes=2),
            iniciado_en=timezone.now(),
        )
    try:
        resultado = registrar_cuenta(
            clabe=cuenta.clabe, transporte=transporte, **payload
        )
        if not _ULID.fullmatch(resultado.id):
            raise ErrorPey("RESPUESTA_INVALIDA", "", puede_haberse_creado=True)
    except ErrorPey as exc:
        incierta = exc.puede_haberse_creado
        _aplicar(
            op,
            {
                "registro_estado": "incierto" if incierta else "rechazado",
                "ultimo_error": _error_seguro(exc),
            },
            "incierta" if incierta else "fallida",
            _error_seguro(exc),
            request_id=re.sub(r"[^A-Za-z0-9_-]", "", exc.request_id or "")[:64],
        )
        raise ErrorOperacion(
            "PEY_INCIERTO" if incierta else "PEY_RECHAZO", 503 if incierta else 502
        ) from None
    campos = {
        "registro_estado": "registrado",
        "pey_bank_account_id": resultado.id,
        "codi_status_crudo": resultado.codi_status,
        "codi_status": "active" if resultado.codi_status == "ACTIVE" else "pending",
        "sincronizada_en": timezone.now(),
        "ultimo_error": "",
    }
    try:
        _aplicar(op, campos, "aplicada", obtenido=resultado.id)
    except IntegrityError:
        _aplicar(
            op,
            {"registro_estado": "incierto", "ultimo_error": "ID_DUPLICADO"},
            "incierta",
            "ID_DUPLICADO",
            obtenido=resultado.id,
        )
        raise ErrorOperacion("PEY_INCIERTO", 503) from None
    cuenta.refresh_from_db()
    return cuenta, False


def _aplicar(op, campos, estado, error="", obtenido="", request_id=""):
    with transaction.atomic():
        cuenta = CuentaCobro.objects.select_related("comercio").get(pk=op.cuenta_id)
        bloquear_comercio_y_demo(cuenta.comercio)
        cuenta = bloquear_cuenta(cuenta)
        actual = OperacionCuenta.objects.select_for_update().get(pk=op.pk)
        if actual.estado != "en_curso":
            return
        ident = campos.get("pey_bank_account_id", cuenta.pey_bank_account_id)
        if id_reservado_demo(ident):
            if "pey_bank_account_id" in campos:
                raise IntegrityError("ID reservado para el demo")
            if campos.get("codi_status") == "active":
                campos = {
                    **campos,
                    "codi_status": "pending",
                    "anomalia": "ID_RESERVADO_DEMO",
                }
        actualizadas = CuentaCobro.objects.filter(
            pk=actual.cuenta_id, version=actual.version_reclamada
        ).update(**campos, version=F("version") + 1)
        OperacionCuenta.objects.filter(pk=actual.pk).update(
            estado=estado if actualizadas else "descartada",
            error=error,
            request_id=request_id,
            pey_bank_account_id_obtenido=obtenido,
            terminado_en=timezone.now(),
            lease_hasta=None,
        )
        if actual.tipo == "sync" and actual.sync_posterior:
            OperacionCuenta.objects.create(
                cuenta_id=actual.cuenta_id,
                tipo="sync",
                origen="webhook",
                estado="pendiente",
            )


def encolar_sync(cuenta: CuentaCobro, origen: str = "webhook"):
    try:
        with transaction.atomic():
            bloquear_comercio(cuenta.comercio)
            cuenta = bloquear_cuenta(cuenta)
            op, _ = OperacionCuenta.objects.get_or_create(
                cuenta=cuenta,
                tipo="sync",
                estado__in=["pendiente", "en_curso"],
                defaults={"estado": "pendiente", "origen": origen},
            )
            if op.estado == "en_curso" and not op.sync_posterior:
                op.sync_posterior = True
                op.save(update_fields=["sync_posterior"])
            return op
    except IntegrityError:
        return cuenta.operaciones.get(tipo="sync", estado__in=["pendiente", "en_curso"])


def sincronizar(cuenta: CuentaCobro, *, transporte=None, op=None):
    with transaction.atomic():
        bloquear_comercio(cuenta.comercio)
        cuenta = bloquear_cuenta(cuenta)
        if not cuenta.pey_bank_account_id:
            raise ErrorOperacion("SIN_REGISTRO_PEY")
        if op is None:
            reciente = (
                cuenta.operaciones.filter(tipo="sync").order_by("-creado_en").first()
            )
            if reciente:
                segundos = 30 - (timezone.now() - reciente.creado_en).total_seconds()
                if segundos > 0:
                    raise ErrorOperacion(
                        "SYNC_PRONTO", 429, reintento_en_segundos=int(segundos) + 1
                    )
            if reciente and reciente.estado == "en_curso":
                raise ErrorOperacion("SYNC_PRONTO", 429, reintento_en_segundos=1)
            if reciente and reciente.estado == "pendiente":
                op = reciente
            else:
                op = OperacionCuenta.objects.create(
                    cuenta=cuenta, tipo="sync", origen="ui", estado="pendiente"
                )
        op = OperacionCuenta.objects.select_for_update().get(pk=op.pk)
        if op.estado != "pendiente":
            return cuenta
        cuenta.version += 1
        cuenta.save(update_fields=["version"])
        op.estado = "en_curso"
        op.version_reclamada = cuenta.version
        op.lease_token = uuid.uuid4()
        op.lease_hasta = timezone.now() + timedelta(minutes=2)
        op.iniciado_en = timezone.now()
        op.save(
            update_fields=[
                "estado",
                "version_reclamada",
                "lease_token",
                "lease_hasta",
                "iniciado_en",
            ]
        )
    try:
        resultado = consultar_cuenta(cuenta.pey_bank_account_id, transporte=transporte)
        coincide = resultado.clabe == cuenta.clabe
        campos = {
            "codi_status_crudo": resultado.codi_status,
            "codi_status": "active"
            if resultado.codi_status == "ACTIVE" and coincide
            else "pending",
            "anomalia": "CLABE_NO_COINCIDE"
            if resultado.codi_status == "ACTIVE" and not coincide
            else "",
            "ultimo_error": "",
            "sincronizada_en": timezone.now(),
        }
        _aplicar(op, campos, "aplicada")
    except (ErrorPey, ParametroInvalido) as exc:
        error = _error_seguro(exc) if isinstance(exc, ErrorPey) else "ID_INVALIDO"
        campos = {"ultimo_error": error}
        if isinstance(exc, ErrorPey) and exc.tipo == "BANK_ACCOUNT_NOT_FOUND":
            campos["codi_status"] = "pending"
        request_id = exc.request_id if isinstance(exc, ErrorPey) else ""
        request_id = re.sub(r"[^A-Za-z0-9_-]", "", request_id or "")[:64]
        _aplicar(op, campos, "fallida", error, request_id=request_id)
    cuenta.refresh_from_db()
    return cuenta


def recuperar_abandonadas():
    for op in OperacionCuenta.objects.filter(
        estado="en_curso", lease_hasta__lt=timezone.now()
    ):
        if op.tipo == "registro":
            _aplicar(op, {"registro_estado": "incierto"}, "incierta")
        else:
            _aplicar(op, {"ultimo_error": "LEASE_VENCIDO"}, "fallida")


def ejecutar_pendientes(detener=None):
    detener = detener or (lambda: False)
    recuperar_abandonadas()
    for op in OperacionCuenta.objects.filter(tipo="sync", estado="pendiente"):
        if detener():
            break
        sincronizar(op.cuenta, op=op)
