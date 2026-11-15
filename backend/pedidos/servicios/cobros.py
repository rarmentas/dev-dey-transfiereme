"""Reserva y transiciones locales del cobro de un pedido."""

import re

from ambito.candados import bloquear_comercio, bloquear_cuenta
from ambito.cuenta import cuenta_apta
from config.modo import cobro_habilitado, modo_de_comercio
from django.db import transaction
from django.db.models import F

from pedidos.contratos.v1 import CodigoError, TipoEvento
from pedidos.contratos.validacion import hash_canonico
from pedidos.errores import ErrorNucleo
from pedidos.models import Aceptacion, IntentoCobro, Pedido
from pedidos.servicios.comandos import guardar, repeticion
from pedidos.servicios.cotizaciones import invalidar
from pedidos.servicios.eventos import emitir
from pedidos.servicios.intentos import plaza_ocupada


def _destino(comercio, demo, importe):
    if demo and importe != 1:
        raise ErrorNucleo(CodigoError.PAYLOAD_INVALIDO)
    cuenta = comercio.cuenta_por_defecto
    if cuenta:
        cuenta = bloquear_cuenta(cuenta)
    if not cuenta_apta(cuenta) or cuenta.comercio_id != comercio.pk:
        raise ErrorNucleo(CodigoError.CUENTA_NO_ACTIVE)
    return cuenta, cuenta.pey_bank_account_id


def _requiere_vencimiento(comercio, pedido, datos, huella):
    with transaction.atomic():
        comercio = bloquear_comercio(comercio)
        if repeticion(comercio, "solicitar_cobro", datos["command_key"], huella):
            return False
        pedido = Pedido.objects.select_for_update().get(pk=pedido.pk, comercio=comercio)
        aceptacion = (
            Aceptacion.objects.select_related("cotizacion")
            .filter(pk=datos["aceptacion_id"], pedido=pedido, comercio=comercio)
            .first()
        )
        previo = (
            IntentoCobro.objects.filter(aceptacion=aceptacion).first()
            if aceptacion
            else None
        )
        if previo:
            intencion = hash_canonico(
                "intencion",
                {
                    "canal": datos["canal"],
                    "telefono": datos.get("telefono_bancario_confirmado") or "",
                },
                "",
            )
            if previo.canal != datos["canal"] or previo.huella_legado != intencion:
                raise ErrorNucleo(CodigoError.INTENCION_DISTINTA)
            return False
        if (
            not aceptacion
            or pedido.estado != "aceptado"
            or aceptacion.cotizacion.revision != pedido.revision_vigente
        ):
            raise ErrorNucleo(CodigoError.ACEPTACION_REQUERIDA)
        if pedido.version != datos["expected_version"]:
            raise ErrorNucleo(CodigoError.VERSION_OBSOLETA)
        if (aceptacion.demo_mode, aceptacion.politica_cobro_version) != (
            modo_de_comercio(comercio)
        ):
            raise ErrorNucleo(CodigoError.MODO_CAMBIO)
        if not cobro_habilitado():
            raise ErrorNucleo(CodigoError.PROVEEDOR_NO_DISPONIBLE)
        return True


def solicitar(comercio, pedido, datos, huella):
    from ventas.canal import vencer_pendientes

    operacion = "solicitar_cobro"
    if _requiere_vencimiento(comercio, pedido, datos, huella):
        vencer_pendientes(comercio)
    with transaction.atomic():
        comercio = bloquear_comercio(comercio)
        replay = repeticion(comercio, operacion, datos["command_key"], huella)
        if replay:
            return replay
        pedido = Pedido.objects.select_for_update().get(pk=pedido.pk, comercio=comercio)
        aceptacion = (
            Aceptacion.objects.select_related("cotizacion")
            .filter(pk=datos["aceptacion_id"], pedido=pedido, comercio=comercio)
            .first()
        )
        telefono = datos.get("telefono_bancario_confirmado") or ""
        intencion = hash_canonico(
            "intencion", {"canal": datos["canal"], "telefono": telefono}, ""
        )
        existente = (
            IntentoCobro.objects.filter(aceptacion=aceptacion).first()
            if aceptacion
            else None
        )
        if existente:
            if (
                existente.canal != datos["canal"]
                or existente.huella_legado != intencion
            ):
                raise ErrorNucleo(CodigoError.INTENCION_DISTINTA)
            resultado = guardar(
                comercio, operacion, datos["command_key"], huella, pedido, replayed=True
            )
            if existente.estado == "en_espera":
                resultado.data["espera"] = "COBRO_OCUPADO"
            return resultado
        if (
            not aceptacion
            or pedido.estado != "aceptado"
            or aceptacion.cotizacion.revision != pedido.revision_vigente
        ):
            raise ErrorNucleo(CodigoError.ACEPTACION_REQUERIDA)
        if pedido.version != datos["expected_version"]:
            raise ErrorNucleo(CodigoError.VERSION_OBSOLETA)
        if (aceptacion.demo_mode, aceptacion.politica_cobro_version) != (
            modo_de_comercio(comercio)
        ):
            raise ErrorNucleo(CodigoError.MODO_CAMBIO)
        if not cobro_habilitado():
            raise ErrorNucleo(CodigoError.PROVEEDOR_NO_DISPONIBLE)
        cuenta, pey_id = _destino(
            comercio, aceptacion.demo_mode, aceptacion.importe_efectivo_centavos
        )
        if datos["canal"] not in ("qr_venta", "notificacion") or (
            datos["canal"] == "notificacion"
            and (
                not isinstance(telefono, str)
                or not re.fullmatch(r"[0-9]{10}", telefono)
            )
        ):
            raise ErrorNucleo(CodigoError.PAYLOAD_INVALIDO)
        ocupado = plaza_ocupada(comercio)
        intento = IntentoCobro.objects.create(
            origen="pedido",
            comercio=comercio,
            pedido=pedido,
            aceptacion=aceptacion,
            cotizacion=aceptacion.cotizacion,
            canal=datos["canal"],
            estado="en_espera" if ocupado else "reservado",
            importe_efectivo_centavos=aceptacion.importe_efectivo_centavos,
            demo_mode=aceptacion.demo_mode,
            politica_cobro_version=aceptacion.politica_cobro_version,
            cuenta=None if ocupado else cuenta,
            pey_bank_account_id="" if ocupado else pey_id,
            concepto=f"Pedido {pedido.numero}",
            referencia="0",
            expiracion_s=600,
            telefono_bancario=telefono,
            huella_legado=intencion,
        )
        pedido.version += 1
        pedido.save(update_fields=["version", "actualizado_en"])
        if ocupado:
            emitir(comercio, pedido, TipoEvento.COBRO_EN_ESPERA, intento=intento)
        resultado = guardar(comercio, operacion, datos["command_key"], huella, pedido)
        if ocupado:
            resultado.data["espera"] = "COBRO_OCUPADO"
        return resultado


def descartar(intento, motivo, *, comercio=None, pedido=None):
    if not IntentoCobro.objects.filter(
        pk=intento.pk, estado__in=["en_espera", "reservado"], version=intento.version
    ).update(
        estado="descartado",
        motivo_descarte=motivo,
        telefono_bancario="",
        version=F("version") + 1,
    ):
        return False
    if intento.pedido_id:
        pedido = pedido or intento.pedido
        comercio = comercio or intento.comercio
        invalidar(comercio, pedido)
        pedido.version += 1
        pedido.save()
        emitir(comercio, pedido, TipoEvento.COBRO_DESCARTADO, intento=intento)
    return True


def activar_espera(comercio, pedido_id, intento_id, datos):
    operacion = "activar_espera"
    huella = hash_canonico(
        operacion,
        {**datos, "pedido_id": str(pedido_id), "intento_id": str(intento_id)},
        str(comercio.pk),
    )
    with transaction.atomic():
        comercio = bloquear_comercio(comercio)
        replay = repeticion(comercio, operacion, datos["command_key"], huella)
        if replay:
            return replay
        pedido = (
            Pedido.objects.select_for_update()
            .filter(pk=pedido_id, comercio=comercio)
            .first()
        )
        intento = (
            IntentoCobro.objects.select_for_update()
            .filter(pk=intento_id, pedido=pedido, comercio=comercio)
            .first()
        )
        if not pedido or not intento:
            raise ErrorNucleo(CodigoError.PEDIDO_NO_ACCESIBLE)
        if intento.estado != "en_espera":
            return guardar(comercio, operacion, datos["command_key"], huella, pedido)
        if pedido.version != datos["expected_version"]:
            raise ErrorNucleo(CodigoError.VERSION_OBSOLETA)
        if (
            pedido.estado != "aceptado"
            or pedido.revision_vigente != intento.cotizacion.revision
            or (intento.demo_mode, intento.politica_cobro_version)
            != modo_de_comercio(comercio)
        ):
            descartar(
                intento,
                "condiciones_cambiaron",
                comercio=comercio,
                pedido=pedido,
            )
            pedido.refresh_from_db()
        else:
            if not cobro_habilitado():
                raise ErrorNucleo(CodigoError.PROVEEDOR_NO_DISPONIBLE)
            cuenta, pey_id = _destino(
                comercio, intento.demo_mode, intento.importe_efectivo_centavos
            )
            if not plaza_ocupada(comercio):
                IntentoCobro.objects.filter(
                    pk=intento.pk, estado="en_espera", version=intento.version
                ).update(
                    estado="reservado",
                    cuenta=cuenta,
                    pey_bank_account_id=pey_id,
                    version=F("version") + 1,
                )
                pedido.version += 1
                pedido.save(update_fields=["version", "actualizado_en"])
        return guardar(comercio, operacion, datos["command_key"], huella, pedido)


def vencer_intento(movimiento):
    from movimientos.models import Movimiento

    from pedidos.servicios.candados import bloquear_para_pago

    intento = IntentoCobro.objects.filter(cobro_id=movimiento.cobro_id).first()
    if not intento:
        with transaction.atomic():
            _, _, _, _, _, movimiento = bloquear_para_pago(
                movimiento.comercio_id,
                cobro_id=movimiento.cobro_id,
                movimiento_id=movimiento.pk,
            )
            if movimiento.estado == Movimiento.Estado.PENDIENTE:
                movimiento.cambiar_estado(Movimiento.Estado.VENCIDO)
        return
    with transaction.atomic():
        comercio, pedido, intento, _, _, movimiento = bloquear_para_pago(
            intento.comercio_id,
            intento.pedido_id,
            intento.pk,
            intento.cuenta_id,
            intento.cobro_id,
            movimiento.pk,
        )
        if movimiento.estado != Movimiento.Estado.PENDIENTE:
            return
        movimiento.cambiar_estado(Movimiento.Estado.VENCIDO)
        if intento.estado == "pendiente":
            IntentoCobro.objects.filter(pk=intento.pk, estado="pendiente").update(
                estado="vencido", version=F("version") + 1
            )
            if pedido:
                pedido.version += 1
                pedido.save(update_fields=["version", "actualizado_en"])
                emitir(comercio, pedido, TipoEvento.COBRO_VENCIDO, intento=intento)
