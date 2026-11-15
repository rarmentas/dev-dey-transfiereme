"""Preparación de escenarios del contrato con persistencia real."""

from django.db import transaction
from django.test import override_settings
from django.utils import timezone

from ambito.models import Comercio
from pedidos.contratos.fixtures import id_determinista
from pedidos.contratos.v1 import (
    ContextoCanalV1,
    MensajeProcedenciaDTO,
    ResumenEnviadoDTO,
    message_key,
)
from pedidos.models import Pedido
from pedidos.servicios.cotizaciones import invalidar
from pedidos.servicios.presentacion import pedido_dto
from pedidos.servicios.tendero import operar
from pedidos.tests.fixtures_v1 import DriverFixtureV1
from ventas.canal import bloquear_comercio


class DriverReal(DriverFixtureV1):
    def __init__(self, lector):
        self.lector = lector
        self.comercios = {}
        self.modo = None
        self.cambiar_modo(False, "normal-1")

    def cerrar(self):
        if self.modo:
            self.modo.disable()

    def cambiar_modo(self, demo, politica):
        self.cerrar()
        self.modo = override_settings(
            DEMO_MODE="true" if demo else "false", POLITICA_COBRO_VERSION=politica
        )
        self.modo.enable()

    def _comercio(self, nombre):
        if nombre not in self.comercios:
            self.comercios[nombre] = Comercio.objects.create(nombre=nombre)
        return self.comercios[nombre]

    def contexto(self, sufijo="", comercio="comercio"):
        ctx = ContextoCanalV1(
            "instancia", "sesion", "chat" + sufijo, "cliente" + sufijo
        )
        self.lector.comercios[(ctx.instancia_id, ctx.sesion_id)] = str(
            self._comercio(comercio).pk
        )
        return ctx

    def cambiar_sesion(self, ctx, sesion, comercio=None):
        identificador = (
            str(self._comercio(comercio).pk)
            if comercio
            else self.lector.resolver_comercio(ctx)
        )
        self.lector.comercios[(ctx.instancia_id, sesion)] = identificador

    def agregar_mensaje(self, ctx, clave, secuencia, texto, tipo="texto"):
        identidad = id_determinista(ctx.conversacion_id, clave)
        llave = message_key(ctx.instancia_id, ctx.sesion_id, clave)
        ahora = timezone.now()
        self.lector.mensajes[(ctx, identidad)] = MensajeProcedenciaDTO(
            identidad, llave, secuencia, tipo, texto, ahora, ahora, True
        )
        return identidad, llave

    def agregar_resumen(self, ctx, cotizacion):
        ahora = timezone.now()
        self.lector.resumenes[(ctx, cotizacion.id)] = ResumenEnviadoDTO(
            id_determinista(cotizacion.id, "salida"),
            "proveedor",
            "enviado",
            cotizacion.id,
            cotizacion.token_resumen,
            cotizacion.revision,
            cotizacion.total_comercial_centavos,
            cotizacion.importe_efectivo_centavos,
            cotizacion.demo_mode,
            cotizacion.politica_cobro_version,
            ctx.cliente_externo_id,
            ahora,
            ahora,
        )

    def publicar_cotizacion(self, pedido_id, renglones):
        pedido = Pedido.objects.get(pk=pedido_id)
        filas = [
            {**r, "resolucion": "incluido", "motivo_exclusion": ""} for r in renglones
        ]
        revision = operar(
            pedido.comercio,
            pedido.id,
            "revisar_renglones",
            {
                "command_key": f"revisar-{pedido.version}",
                "expected_version": pedido.version,
                "renglones": filas,
            },
        )
        return operar(
            pedido.comercio,
            pedido.id,
            "publicar_cotizacion",
            {
                "command_key": f"publicar-{pedido.version}",
                "expected_version": revision.data["pedido"].version,
            },
        ).data["pedido"]

    def invalidar_cotizacion(self, pedido_id):
        with transaction.atomic():
            comercio = bloquear_comercio(Pedido.objects.get(pk=pedido_id).comercio)
            pedido = Pedido.objects.select_for_update().get(pk=pedido_id)
            pedido.version += 1
            invalidar(comercio, pedido)
            pedido.save()
            return pedido_dto(pedido)
