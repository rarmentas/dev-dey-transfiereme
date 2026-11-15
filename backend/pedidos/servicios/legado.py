"""Fachada síncrona idempotente para las ventas anteriores."""

import re

from ambito.candados import bloquear_comercio, bloquear_cuenta
from ambito.cuenta import cuenta_apta
from config.modo import modo_de_comercio
from django.db import transaction
from movimientos.exceptions import DemoBloqueado
from pey.tipos import ErrorPey, ParametroInvalido
from ventas.canal import VentaPendiente, vencer_pendientes, venta_viva
from ventas.servicio import CuentaNoActive, VentaCreada

from pedidos.contratos.validacion import hash_canonico
from pedidos.models import IntentoCobro
from pedidos.servicios.despacho import enviar_intento
from pedidos.servicios.intentos import plaza_ocupada


class ClaveReutilizada(Exception):
    """La clave ya corresponde a otra solicitud."""


class CobroEnCurso(Exception):
    """Un cobro sin resultado definitivo bloquea la emisión."""

    def __init__(self, intento):
        self.intento = intento


class CobroInciertoEnvio(CobroEnCurso):
    """El envío recién realizado no obtuvo una respuesta definitiva."""


def _resultado(intento):
    if intento.estado in ("enviando", "incierto", "reservado"):
        raise CobroEnCurso(intento)
    if intento.cobro_id:
        cobro = intento.cobro
        movimiento = cobro.movimientos.get()
        movimiento.estado = "pendiente"
        return VentaCreada(
            movimiento, cobro, cobro.qr_string, cobro.pey_transaction_id or ""
        )
    if intento.error == "ParametroInvalido":
        raise ParametroInvalido("Parámetros rechazados por el proveedor.")
    raise ErrorPey(
        intento.error or "RECHAZADO",
        "El proveedor rechazó el cobro.",
        request_id=intento.request_id or None,
    )


def emitir_legado(
    comercio, canal, monto, concepto, referencia, telefono, clave, puerto
):
    if not isinstance(clave, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", clave):
        raise ValueError("Idempotency-Key es obligatoria.")
    huella = hash_canonico(
        "venta",
        {
            "canal": canal,
            "monto": str(monto),
            "concepto": concepto,
            "referencia": referencia,
            "telefono": telefono,
        },
        str(comercio.pk),
    )
    vencer_pendientes(comercio)
    with transaction.atomic():
        comercio = bloquear_comercio(comercio)
        modo = modo_de_comercio(comercio)
        if modo.demo:
            raise DemoBloqueado()
        anterior = IntentoCobro.objects.filter(
            comercio=comercio, clave_legado=clave
        ).first()
        if anterior:
            if anterior.huella_legado != huella:
                raise ClaveReutilizada()
            if anterior.estado == "incierto":
                raise CobroInciertoEnvio(anterior)
            return _resultado(anterior)
        cuenta = comercio.cuenta_por_defecto
        if cuenta:
            cuenta = bloquear_cuenta(cuenta)
        if not cuenta_apta(cuenta) or cuenta.comercio_id != comercio.pk:
            raise CuentaNoActive()
        if plaza_ocupada(comercio):
            movimiento = venta_viva(comercio)
            if movimiento:
                raise VentaPendiente(movimiento)
            raise CobroEnCurso(
                IntentoCobro.objects.get(
                    comercio=comercio,
                    estado__in=("reservado", "enviando", "pendiente", "incierto"),
                )
            )
        intento = IntentoCobro.objects.create(
            origen="legado",
            comercio=comercio,
            canal=canal,
            estado="reservado",
            importe_efectivo_centavos=int(monto * 100),
            demo_mode=False,
            politica_cobro_version=modo.politica,
            cuenta=cuenta,
            pey_bank_account_id=cuenta.pey_bank_account_id,
            concepto=concepto,
            referencia=referencia,
            expiracion_s=600,
            telefono_bancario=telefono,
            clave_legado=clave,
            huella_legado=huella,
        )
    enviado = enviar_intento(intento.pk, puerto)
    if enviado.estado == "incierto":
        raise CobroInciertoEnvio(enviado)
    return _resultado(enviado)
