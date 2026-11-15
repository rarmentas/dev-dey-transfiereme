"""Preparación de escenarios del contrato con persistencia real."""

import json
import uuid

from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import Client
from unittest.mock import patch

from config import modo
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
    def __init__(self, lector, cobros=False):
        self.cobros = cobros
        self.puerto = None
        self.temprano_id = None
        if cobros:
            from pedidos.tests.soporte_cobro import PuertoPeyFalso

            self.puerto = PuertoPeyFalso()
        self.lector = lector
        self.comercios = {}
        self.modo = None
        self.demo_actual = False


    def cerrar(self):
        if self.modo:
            self.modo.stop()
            self.modo = None

    def cambiar_modo(self, demo, politica):
        self.cerrar()
        self.demo_actual = demo
        Comercio.objects.filter(pk__in=[c.pk for c in self.comercios.values()]).update(
            es_demo=False
        )
        comercio = self.comercios.get("comercio")
        if comercio:
            Comercio.objects.filter(pk=comercio.pk).update(es_demo=demo)
        if politica != modo.politica_de(demo):
            self.modo = patch.object(
                modo, "POLITICA_DEMO" if demo else "POLITICA_NORMAL", politica
            )
            self.modo.start()
        if self.cobros and self.comercios:
            self.despachar()

    def _comercio(self, nombre):
        if nombre not in self.comercios:
            self.comercios[nombre] = Comercio.objects.create(
                nombre=nombre, es_demo=self.demo_actual and nombre == "comercio"
            )
            if self.cobros:
                from ambito.tests.soporte import crear_cuenta

                crear_cuenta(self.comercios[nombre])
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
                "command_key": f"revisar-{pedido.id}-{pedido.version}",
                "expected_version": pedido.version,
                "renglones": filas,
            },
        )
        return operar(
            pedido.comercio,
            pedido.id,
            "publicar_cotizacion",
            {
                "command_key": f"publicar-{pedido.id}-{pedido.version}",
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


    def fijar_cuenta(self, estado):
        comercio = self._comercio("comercio")
        cuenta = comercio.cuenta_por_defecto
        cuenta.codi_status = "active" if estado == "active" else "pending"
        cuenta.save(update_fields=["codi_status"])

    def ocupar_comercio(self, comercio="comercio"):
        from pedidos.models import IntentoCobro

        comercio = self._comercio(comercio)
        cuenta = comercio.cuenta_por_defecto
        IntentoCobro.objects.create(
            origen="legado",
            comercio=comercio,
            canal="qr_venta",
            estado="reservado",
            cuenta=cuenta,
            pey_bank_account_id=cuenta.pey_bank_account_id,
            importe_efectivo_centavos=100,
            demo_mode=False,
            politica_cobro_version="normal-1",
            concepto="ocupado",
            expiracion_s=600,
            clave_legado="fixture-ocupado",
        )

    def liberar_comercio(self, comercio="comercio"):
        from pedidos.models import IntentoCobro

        IntentoCobro.objects.filter(
            comercio=self._comercio(comercio), origen="legado", estado="reservado"
        ).update(estado="descartado")

    def forzar_incierto(self):
        from pey.tipos import ErrorPey

        self.puerto.fallar_con = ErrorPey(
            "NO_DISPONIBLE", "timeout", puede_haberse_creado=True
        )

    def despachar(self):
        from pedidos.models import IntentoCobro
        from pedidos.servicios.despacho import enviar_intento

        for intento in IntentoCobro.objects.filter(origen="pedido", estado="reservado"):
            self.puerto.siguiente_id = self.temprano_id or str(uuid.uuid4())
            self.temprano_id = None
            enviar_intento(intento.pk, self.puerto)

    def contar_llamadas(self):
        return len(self.puerto.llamadas)

    def _aviso(self, qr, webhook_id, banco, monto, transaction_id):
        from webhooks.tests.support.pey_webhook import post_firmado

        cuerpo = json.dumps(
            {
                "type": "codi.qr.payment_received",
                "amount": monto,
                "codiQrId": qr,
                "transactionId": transaction_id,
                "bankAccountId": banco,
            },
            separators=(",", ":"),
        )
        return post_firmado(Client(), cuerpo, webhook_id)

    def confirmar_pago(self, pedido_id, webhook_id):
        from pedidos.models import IntentoCobro

        intento = IntentoCobro.objects.get(pedido_id=pedido_id)
        self._aviso(
            intento.cobro.pey_qr_id,
            webhook_id,
            intento.pey_bank_account_id,
            float(intento.cobro.monto),
            str(uuid.uuid5(uuid.NAMESPACE_URL, pedido_id)),
        )
        return pedido_dto(Pedido.objects.get(pk=pedido_id))

    def webhook_temprano(self, cobro_id, webhook_id):
        self.temprano_id = cobro_id
        cuenta = self._comercio("comercio").cuenta_por_defecto
        self._aviso(
            cobro_id,
            webhook_id,
            cuenta.pey_bank_account_id,
            25,
            str(uuid.uuid5(uuid.NAMESPACE_URL, cobro_id)),
        )

    def _entrega(self, pedido_id, entregado=False):
        from pedidos.errores import ErrorNucleo
        from pedidos.servicios.entrega import operar as entregar

        pedido = Pedido.objects.get(pk=pedido_id)
        usuario, _ = get_user_model().objects.get_or_create(username="fixture-tendero")
        try:
            resultado = entregar(
                pedido.comercio,
                pedido.pk,
                {
                    "command_key": "entregado" if entregado else "listo",
                    "expected_version": pedido.version,
                },
                usuario,
                entregado=entregado,
            )
        except ErrorNucleo as exc:
            raise ValueError("Entrega inválida") from exc
        return resultado.data["pedido"]

    def marcar_listo(self, pedido_id):
        return self._entrega(pedido_id)

    def marcar_entregado(self, pedido_id):
        return self._entrega(pedido_id, entregado=True)

    def activar_intento_en_espera(
        self, pedido_id, intento_id, expected_version, command_key
    ):
        from pedidos.servicios.cobros import activar_espera

        pedido = Pedido.objects.get(pk=pedido_id)
        resultado = activar_espera(
            pedido.comercio,
            pedido.pk,
            intento_id,
            {"expected_version": expected_version, "command_key": command_key},
        )
        self.despachar()
        return pedido_dto(Pedido.objects.get(pk=pedido_id)) if resultado.ok else None

    def reservar_sin_envio(self, pedido_id):
        from pedidos.contratos.validacion import hash_canonico
        from pedidos.servicios.cobros import solicitar

        pedido = Pedido.objects.get(pk=pedido_id)
        aceptacion = pedido.cotizaciones.get(
            revision=pedido.revision_vigente
        ).aceptacion
        datos = {
            "contrato_version": "1.0",
            "command_key": "reservar",
            "pedido_id": str(pedido.pk),
            "expected_version": pedido.version,
            "aceptacion_id": str(aceptacion.pk),
            "canal": "qr_venta",
        }
        return solicitar(
            pedido.comercio,
            pedido,
            datos,
            hash_canonico("solicitar_cobro", datos, "fixture"),
        ).data["pedido"]

    def audio_fallido(self, ctx, mensaje_id):
        from canales.conversacion import procesar_mensaje
        from canales.models import (
            ConversacionCanal,
            MensajeEntrante,
            SalidaCanal,
            SesionCanal,
            TrabajoAudio,
        )
        from pedidos.nucleo_real import NucleoRealV1

        sesion, _ = SesionCanal.objects.get_or_create(
            instancia_id=ctx.instancia_id, sesion_id=ctx.sesion_id,
            defaults={"comercio": self._comercio("comercio")},
        )
        conversacion, _ = ConversacionCanal.objects.get_or_create(
            sesion=sesion, chat_id=ctx.conversacion_id,
            defaults={"cliente_externo_id": ctx.cliente_externo_id},
        )
        mensaje, _ = MensajeEntrante.objects.get_or_create(
            pk=mensaje_id,
            defaults={
                "conversacion": conversacion, "instancia_id": ctx.instancia_id,
                "sesion_id": ctx.sesion_id, "id_mensaje_proveedor": str(mensaje_id),
                "hash_payload": "fixture", "secuencia": 2, "tipo": "audio",
            },
        )
        TrabajoAudio.objects.get_or_create(
            mensaje=mensaje, defaults={"estado": "fallido", "vence_en": timezone.now()}
        )
        procesar_mensaje(
            mensaje, NucleoRealV1(self.lector), self.lector, timezone.now()
        )
        return SalidaCanal.objects.get(causa=f"mensaje:{mensaje.id}").payload["texto"]
