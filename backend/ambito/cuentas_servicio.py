"""Alta y selección de cuentas del comercio."""

from django.db import IntegrityError, transaction

from ambito.candados import bloquear_comercio, bloquear_cuenta
from ambito.clabe import clabe_es_valida
from ambito.cuenta import cuenta_apta
from ambito.cuenta_pey_servicio import enmascarar_clabe, sufijo_ulid
from ambito.models import CuentaCobro
from ambito.operaciones_cuenta import ErrorOperacion


def alta(comercio, clabe):
    if not clabe_es_valida(clabe):
        raise ErrorOperacion("CLABE_INVALIDA", 400)
    try:
        with transaction.atomic():
            return CuentaCobro.objects.create(comercio=comercio, clabe=clabe)
    except IntegrityError:
        raise ErrorOperacion("CLABE_DUPLICADA") from None


def elegir_default(comercio, cuenta, version):
    with transaction.atomic():
        comercio = bloquear_comercio(comercio)
        cuenta = bloquear_cuenta(cuenta)
        if cuenta.comercio_id != comercio.pk:
            raise ErrorOperacion("CUENTA_NO_ENCONTRADA", 404)
        if type(version) is not int or cuenta.version != version:
            raise ErrorOperacion("VERSION_OBSOLETA")
        if not cuenta_apta(cuenta):
            raise ErrorOperacion("CUENTA_NO_ELEGIBLE")
        comercio.cuenta_por_defecto = cuenta
        comercio.save(update_fields=["cuenta_por_defecto"])
    return cuenta


def cuenta_dict(cuenta, comercio):
    op = cuenta.operaciones.order_by("-creado_en").first()
    return {
        "id": str(cuenta.pk),
        "clabe_enmascarada": enmascarar_clabe(cuenta.clabe),
        "registro_estado": cuenta.registro_estado,
        "codi_status": cuenta.codi_status,
        "es_predeterminada": comercio.cuenta_por_defecto_id == cuenta.pk,
        "puede_cobrar": cuenta_apta(cuenta),
        "pey_id_sufijo": sufijo_ulid(cuenta.pey_bank_account_id),
        "sincronizada_en": cuenta.sincronizada_en.isoformat()
        if cuenta.sincronizada_en
        else None,
        "ultimo_error": cuenta.ultimo_error,
        "anomalia": cuenta.anomalia,
        "version": cuenta.version,
        "operacion": {"tipo": op.tipo, "estado": op.estado} if op else None,
    }
