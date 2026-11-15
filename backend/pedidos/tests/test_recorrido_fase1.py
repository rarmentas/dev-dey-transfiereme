"""Recorrido de solicitud, aceptación y confirmación bancaria firmada."""

import json

from ambito.tests.soporte import crear_cuenta
from django.test import Client, override_settings
from movimientos.models import Cobro, Movimiento
from webhooks.tests.support.pey_webhook import SECRETO, post_firmado

from pedidos.contratos.fixtures import id_determinista
from pedidos.contratos.v1 import CodigoError, RenglonSolicitadoV1
from pedidos.models import Aceptacion, EventoPedido, IntentoCobro, Pedido
from pedidos.servicios.despacho import enviar_intento
from pedidos.tests.soporte_cobro import PuertoPeyFalso
from pedidos.tests.soporte_real import CasoReal


@override_settings(PEDIDOS_COBRO_HABILITADO=True, PEY_WEBHOOK_SECRET=SECRETO)
class RecorridoFase1Tests(CasoReal):
    def test_solo_webhook_firmado_paga_y_repeticiones_no_duplican(self):
        ctx, solicitud, pedido = self.crear()
        repetida = self.nucleo.registrar_solicitud(ctx, **solicitud)
        self.assertTrue(repetida.replayed)
        pedido = self.cotizar(ctx, pedido)
        datos = self.datos_aceptacion(ctx, pedido)
        aceptado = self.nucleo.aceptar_cotizacion(ctx, **datos)
        self.assertTrue(aceptado.ok, aceptado.error)
        self.assertTrue(self.nucleo.aceptar_cotizacion(ctx, **datos).replayed)
        pedido = aceptado.data["pedido"]
        cuenta = crear_cuenta(self.driver._comercio("comercio"))
        cobro = dict(
            contrato_version="1.0",
            command_key="cobro",
            pedido_id=pedido.id,
            expected_version=pedido.version,
            aceptacion_id=pedido.aceptacion.id,
            canal="qr_venta",
        )
        self.assertTrue(self.nucleo.solicitar_cobro(ctx, **cobro).ok)
        self.assertTrue(self.nucleo.solicitar_cobro(ctx, **cobro).replayed)
        intento = IntentoCobro.objects.get()
        enviar_intento(intento.pk, PuertoPeyFalso())
        intento.refresh_from_db()
        self.assertEqual(intento.estado, "pendiente")
        movimiento = Movimiento.objects.get(cobro=intento.cobro)
        self.assertEqual(movimiento.estado, "pendiente")
        for clave, texto, tipo, secuencia in (
            ("texto-pago", "ya pagué", "texto", 3),
            ("captura", "", "imagen", 4),
        ):
            mensaje, llave = self.driver.agregar_mensaje(
                ctx, clave, secuencia, texto, tipo
            )
            resultado = self.nucleo.corregir_borrador(
                ctx,
                contrato_version="1.0",
                command_key=clave,
                pedido_id=pedido.id,
                expected_version=Pedido.objects.get(pk=pedido.id).version,
                mensaje_id=mensaje,
                message_key=llave,
                secuencia_conversacion=secuencia,
                renglones=[RenglonSolicitadoV1(id_determinista(clave, "r"), "leche")],
            )
            self.assertFalse(resultado.ok)
            self.assertIn(
                resultado.error.code,
                (CodigoError.PEDIDO_CONGELADO, CodigoError.CONTEXTO_INVALIDO),
            )
            movimiento.refresh_from_db()
            self.assertEqual(movimiento.estado, "pendiente")
        cuerpo = json.dumps(
            {
                "type": "codi.qr.payment_received",
                "amount": 25,
                "transactionId": "pago-recorrido",
                "codiQrId": "qr-prueba",
                "bankAccountId": cuenta.pey_bank_account_id,
            },
            separators=(",", ":"),
        )
        cliente = Client()
        self.assertEqual(
            post_firmado(cliente, cuerpo, "recorrido").json()["estado"], "aplicado"
        )
        self.assertEqual(
            post_firmado(cliente, cuerpo, "recorrido").json()["estado"], "duplicado"
        )
        intento.refresh_from_db()
        movimiento.refresh_from_db()
        self.assertEqual(intento.estado, "pagado")
        self.assertEqual(movimiento.estado, "pagado")
        self.assertEqual(Pedido.objects.count(), 1)
        self.assertEqual(Aceptacion.objects.count(), 1)
        self.assertEqual(IntentoCobro.objects.count(), 1)
        self.assertEqual(Cobro.objects.count(), 1)
        self.assertEqual(Movimiento.objects.count(), 1)
        for tipo in (
            "pedido.creado",
            "cotizacion.publicada",
            "pedido.aceptado",
            "cobro.pendiente",
            "pago.confirmado",
        ):
            self.assertEqual(EventoPedido.objects.filter(tipo=tipo).count(), 1)
