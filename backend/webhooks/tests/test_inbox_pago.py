"""Confirmación firmada y correlación de pagos de pedidos."""

import json
from unittest.mock import patch

from ambito.tests.soporte import crear_cuenta
from django.test import Client, override_settings
from movimientos.models import Movimiento
from pedidos.models import EventoPedido, IntentoCobro, Pedido
from pedidos.servicios.despacho import enviar_intento
from pedidos.tests.soporte_cobro import PuertoPeyFalso
from pedidos.tests.soporte_real import CasoReal

from webhooks.models import AvisoRecibido
from webhooks.tests.support.pey_webhook import SECRETO, post_firmado


@override_settings(PEDIDOS_COBRO_HABILITADO=True, PEY_WEBHOOK_SECRET=SECRETO)
class InboxPagoTests(CasoReal):
    def setUp(self):
        super().setUp()
        self.ctx, _, pedido = self.crear()
        pedido = self.cotizar(self.ctx, pedido)
        self.pedido = self.nucleo.aceptar_cotizacion(
            self.ctx, **self.datos_aceptacion(self.ctx, pedido)
        ).data["pedido"]
        self.comercio = self.driver._comercio("comercio")
        self.cuenta = crear_cuenta(self.comercio)
        self.puerto = PuertoPeyFalso()
        self.cliente = Client()

    def reservar(self):
        resultado = self.nucleo.solicitar_cobro(
            self.ctx,
            contrato_version="1.0",
            command_key="cobro",
            pedido_id=self.pedido.id,
            expected_version=self.pedido.version,
            aceptacion_id=self.pedido.aceptacion.id,
            canal="qr_venta",
        )
        self.assertTrue(resultado.ok, resultado.error)
        return IntentoCobro.objects.get(pedido_id=self.pedido.id)

    def cuerpo(self, *, qr="qr-prueba", monto=25, banco=None, tx="transaccion"):
        return json.dumps(
            {
                "type": "codi.qr.payment_received",
                "amount": monto,
                "transactionId": tx,
                "codiQrId": qr,
                "bankAccountId": banco
                if banco is not None
                else self.cuenta.pey_bank_account_id,
            },
            separators=(",", ":"),
        )

    def post(self, cuerpo, clave="webhook"):
        return post_firmado(self.cliente, cuerpo, clave)

    def test_firma_monto_destino_e_id_ajenos_no_pagan(self):
        intento = self.reservar()
        enviar_intento(intento.pk, self.puerto)
        cuerpo = self.cuerpo()
        falso = self.cliente.post(
            "/api/webhooks/pey/",
            data=cuerpo,
            content_type="application/json",
            HTTP_WEBHOOK_ID="falso",
            HTTP_WEBHOOK_TIMESTAMP="0",
            HTTP_WEBHOOK_SIGNATURE="v1,falso",
        )
        self.assertEqual(falso.status_code, 401)
        self.assertEqual(
            self.post(self.cuerpo(monto=26), "monto").json()["estado"], "monto_distinto"
        )
        self.assertEqual(
            self.post(
                self.cuerpo(banco="01ARZ3NDEKTSV4RRFFQ69G5FAV"), "destino"
            ).json()["estado"],
            "destino_distinto",
        )
        self.assertEqual(
            self.post(self.cuerpo(qr="desconocido"), "ajeno").json()["estado"],
            "pendiente_correlacion",
        )
        intento.refresh_from_db()
        self.assertEqual(intento.estado, "pendiente")
        self.assertEqual(
            Movimiento.objects.get(cobro=intento.cobro).estado, "pendiente"
        )
        self.assertFalse(EventoPedido.objects.filter(tipo="pago.confirmado").exists())
        self.assertFalse(AvisoRecibido.objects.filter(webhook_id="falso").exists())

    def test_temprano_se_reaplica_y_duplicados_un_evento(self):
        intento = self.reservar()
        cuerpo = self.cuerpo()
        self.assertEqual(self.post(cuerpo).json()["estado"], "pendiente_correlacion")
        enviar_intento(intento.pk, self.puerto)
        intento.refresh_from_db()
        self.assertEqual(intento.estado, "pagado")
        self.assertEqual(self.post(cuerpo).json()["estado"], "duplicado")
        self.assertEqual(
            self.post(cuerpo, "otro").json()["estado"], "duplicado_transaccion"
        )
        self.assertEqual(Movimiento.objects.filter(estado="pagado").count(), 1)
        self.assertEqual(EventoPedido.objects.filter(tipo="pago.confirmado").count(), 1)
        self.assertEqual(
            AvisoRecibido.objects.get(webhook_id="webhook").correlacion,
            "correlacionado",
        )

    def test_fallo_evento_revierte_movimiento_intento_y_aviso(self):
        intento = self.reservar()
        enviar_intento(intento.pk, self.puerto)
        with patch(
            "pedidos.servicios.pagos.emitir", side_effect=RuntimeError("evento")
        ):
            with self.assertRaises(RuntimeError):
                self.post(self.cuerpo())
        intento.refresh_from_db()
        self.assertEqual(intento.estado, "pendiente")
        self.assertEqual(
            Movimiento.objects.get(cobro=intento.cobro).estado, "pendiente"
        )
        self.assertFalse(AvisoRecibido.objects.filter(webhook_id="webhook").exists())
        self.assertFalse(EventoPedido.objects.filter(tipo="pago.confirmado").exists())

    def test_pago_tardio_preserva_cuenta_y_pedido(self):
        from pedidos.servicios.cobros import vencer_intento

        intento = self.reservar()
        enviar_intento(intento.pk, self.puerto)
        intento.refresh_from_db()
        vencer_intento(Movimiento.objects.get(cobro=intento.cobro))
        crear_cuenta(self.comercio)
        self.assertEqual(self.post(self.cuerpo()).json()["estado"], "aplicado")
        intento.refresh_from_db()
        self.assertEqual(intento.estado, "pagado")
        self.assertEqual(intento.cuenta_id, self.cuenta.pk)
        self.assertEqual(intento.pedido_id, Pedido.objects.get(pk=self.pedido.id).pk)
        self.assertEqual(intento.cobro.cuenta_id, self.cuenta.pk)

    def test_webhooks_concurrentes_de_misma_transaccion_solo_un_pago(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier

        from django.db import connections

        intento = self.reservar()
        enviar_intento(intento.pk, self.puerto)
        cuerpo = self.cuerpo()
        barrera = Barrier(2)

        def recibir(indice):
            try:
                barrera.wait(timeout=10)
                return post_firmado(Client(), cuerpo, f"concurrente-{indice}").json()[
                    "estado"
                ]
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as ejecutor:
            estados = list(ejecutor.map(recibir, range(2)))
        self.assertCountEqual(estados, ["aplicado", "duplicado_transaccion"])
        intento.refresh_from_db()
        self.assertEqual(intento.estado, "pagado")
        self.assertEqual(Movimiento.objects.filter(estado="pagado").count(), 1)
        self.assertEqual(EventoPedido.objects.filter(tipo="pago.confirmado").count(), 1)

    def test_mismo_webhook_id_concurrente_se_aplica_una_vez(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier

        from django.db import connections

        intento = self.reservar()
        enviar_intento(intento.pk, self.puerto)
        cuerpo = self.cuerpo()
        barrera = Barrier(2)

        def recibir(_indice):
            try:
                barrera.wait(timeout=10)
                return post_firmado(Client(), cuerpo, "mismo-id").json()["estado"]
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as ejecutor:
            estados = list(ejecutor.map(recibir, range(2)))
        self.assertCountEqual(estados, ["aplicado", "duplicado"])
        self.assertEqual(AvisoRecibido.objects.filter(webhook_id="mismo-id").count(), 1)
        self.assertEqual(Movimiento.objects.filter(estado="pagado").count(), 1)
        self.assertEqual(EventoPedido.objects.filter(tipo="pago.confirmado").count(), 1)

    def test_cobro_historico_sin_snapshot_conserva_correlacion_etiquetada(self):
        from decimal import Decimal

        from movimientos.models import Cobro

        cobro = Cobro.objects.create(
            comercio=self.comercio,
            canal="qr_venta",
            monto=Decimal("25.00"),
            concepto="Histórico",
            pey_qr_id="historico",
            qr_string="qr",
            pey_bank_account_id="",
        )
        movimiento = Movimiento.objects.create(
            comercio=self.comercio,
            cobro=cobro,
            canal="qr_venta",
            monto=Decimal("25.00"),
            concepto="Histórico",
            origen="origen_pey",
        )
        respuesta = self.post(self.cuerpo(qr="historico", banco=""), "historico")
        self.assertEqual(respuesta.json()["estado"], "aplicado")
        movimiento.refresh_from_db()
        self.assertEqual(movimiento.estado, "pagado")
        aviso = AvisoRecibido.objects.get(webhook_id="historico")
        self.assertEqual(aviso.razon, "destino_historico_sin_snapshot")

    def test_resolver_enlaza_y_reaplica_aviso_ya_firmado(self):
        from django.core.management import call_command
        from pey.tipos import ErrorPey

        intento = self.reservar()
        self.puerto.fallar_con = ErrorPey(
            "NO_DISPONIBLE", "timeout", puede_haberse_creado=True
        )
        enviar_intento(intento.pk, self.puerto)
        self.assertEqual(
            self.post(self.cuerpo()).json()["estado"], "pendiente_correlacion"
        )
        call_command(
            "resolver_intento",
            intento=str(intento.pk),
            accion="enlazar",
            qr_id="qr-prueba",
            confirmar=True,
        )
        intento.refresh_from_db()
        self.assertEqual(intento.estado, "pagado")
        self.assertEqual(Movimiento.objects.get(cobro=intento.cobro).estado, "pagado")
        self.assertEqual(EventoPedido.objects.filter(tipo="pago.confirmado").count(), 1)

    def test_persiste_solo_datos_normalizados_y_hash(self):
        intento = self.reservar()
        enviar_intento(intento.pk, self.puerto)
        datos = json.loads(self.cuerpo())
        datos["datePaid"] = "2026-01-01T12:00:00Z"
        datos["metadata"] = {"clabe": "123456789012345678"}
        cuerpo = json.dumps(datos, separators=(",", ":"))
        self.assertEqual(self.post(cuerpo).json()["estado"], "aplicado")
        aviso = AvisoRecibido.objects.get(webhook_id="webhook")
        self.assertEqual(aviso.bank_account_id, self.cuenta.pey_bank_account_id)
        self.assertEqual(aviso.fecha_pago.isoformat(), "2026-01-01T12:00:00+00:00")
        self.assertIsNotNone(aviso.verificado_en)
        self.assertEqual(len(aviso.payload_hash), 64)
        valores = [str(getattr(aviso, f.attname)) for f in aviso._meta.concrete_fields]
        self.assertFalse(any("123456789012345678" in valor for valor in valores))
        self.assertFalse(any(cuerpo in valor for valor in valores))

    def test_bank_account_no_texto_o_ulid_invalido_se_rechaza(self):
        for indice, valor in enumerate((0, None, "invalido", "A" * 27)):
            datos = json.loads(self.cuerpo())
            datos["bankAccountId"] = valor
            respuesta = self.post(json.dumps(datos), f"bank-invalido-{indice}")
            self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(AvisoRecibido.objects.count(), 0)
        self.assertEqual(Movimiento.objects.count(), 0)

    def test_pedido_en_espera_no_recibe_pago_por_monto(self):
        IntentoCobro.objects.create(
            origen="legado",
            comercio=self.comercio,
            canal="qr_venta",
            estado="reservado",
            importe_efectivo_centavos=100,
            demo_mode=False,
            politica_cobro_version="normal-1",
            cuenta=self.cuenta,
            pey_bank_account_id=self.cuenta.pey_bank_account_id,
            concepto="ocupado",
            expiracion_s=600,
            clave_legado="ocupado",
        )
        espera = self.reservar()
        self.assertEqual(espera.estado, "en_espera")
        respuesta = self.post(self.cuerpo(qr="id-desconocido"))
        self.assertEqual(respuesta.json()["estado"], "pendiente_correlacion")
        espera.refresh_from_db()
        self.assertEqual(espera.estado, "en_espera")
        self.assertIsNone(espera.cobro_id)
        self.assertFalse(Movimiento.objects.filter(estado="pagado").exists())
        self.assertFalse(EventoPedido.objects.filter(tipo="pago.confirmado").exists())

    def test_replay_fallido_no_revierte_el_cobro_y_se_recupera(self):
        from pedidos.servicios.pagos import reaplicar_pendientes

        intento = self.reservar()
        self.assertEqual(
            self.post(self.cuerpo()).json()["estado"], "pendiente_correlacion"
        )
        with patch(
            "pedidos.servicios.pagos.emitir", side_effect=RuntimeError("evento")
        ):
            enviar_intento(intento.pk, self.puerto)
        intento.refresh_from_db()
        self.assertIsNotNone(intento.cobro_id)
        self.assertEqual(intento.estado, "pendiente")
        self.assertEqual(AvisoRecibido.objects.get().correlacion, "pendiente")
        self.assertEqual(
            Movimiento.objects.get(cobro=intento.cobro).estado, "pendiente"
        )
        reaplicar_pendientes(intento.cobro)
        intento.refresh_from_db()
        self.assertEqual(intento.estado, "pagado")
        self.assertEqual(EventoPedido.objects.filter(tipo="pago.confirmado").count(), 1)

    def test_aplicacion_interna_sin_inbox_no_puede_pagar_intento(self):
        from decimal import Decimal

        from movimientos.correlacion import AvisoPago, aplicar_aviso
        from movimientos.exceptions import AvisoInvalido

        intento = self.reservar()
        enviar_intento(intento.pk, self.puerto)
        aviso = AvisoPago(
            "codi.qr.payment_received", Decimal("25.00"), "sin-firma", "qr-prueba"
        )
        with self.assertRaises(AvisoInvalido):
            aplicar_aviso(aviso, origen=Movimiento.Origen.ORIGEN_PEY)
        intento.refresh_from_db()
        self.assertEqual(intento.estado, "pendiente")
        self.assertEqual(
            Movimiento.objects.get(cobro=intento.cobro).estado, "pendiente"
        )
        self.assertFalse(EventoPedido.objects.filter(tipo="pago.confirmado").exists())

    def test_i1_worker_reaplica_fallo_aun_con_compuerta_cerrada(self):
        from pedidos.servicios.despacho import ciclo

        intento = self.reservar()
        self.assertEqual(
            self.post(self.cuerpo()).json()["estado"], "pendiente_correlacion"
        )
        with patch(
            "pedidos.servicios.pagos.emitir", side_effect=RuntimeError("evento")
        ):
            enviar_intento(intento.pk, self.puerto)
        with (
            override_settings(PEDIDOS_COBRO_HABILITADO=False),
            patch("ambito.operaciones_cuenta.recuperar_abandonadas"),
            patch("ambito.operaciones_cuenta.ejecutar_pendientes"),
        ):
            ciclo(self.puerto)
        intento.refresh_from_db()
        self.assertEqual(intento.estado, "pagado")
        self.assertEqual(Movimiento.objects.get(cobro=intento.cobro).estado, "pagado")
        self.assertEqual(EventoPedido.objects.filter(tipo="pago.confirmado").count(), 1)
        self.assertEqual(len(self.puerto.llamadas), 1)

    def test_i1_carrera_aviso_no_visible_se_recupera_con_ciclo(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event, current_thread, main_thread

        from django.db import connections

        from pedidos.servicios import pagos
        from pedidos.servicios.despacho import ciclo

        intento = self.reservar()
        cuerpo = self.cuerpo()
        localizado = Event()
        continuar = Event()
        original = pagos._localizar

        def localizar(aviso):
            resultado = original(aviso)
            if current_thread() is not main_thread():
                localizado.set()
                if not continuar.wait(10):
                    raise TimeoutError("No se liberó el aviso")
            return resultado

        def recibir():
            try:
                return post_firmado(Client(), cuerpo, "carrera-commit").json()["estado"]
            finally:
                connections.close_all()

        with patch("pedidos.servicios.pagos._localizar", side_effect=localizar):
            with ThreadPoolExecutor(max_workers=1) as ejecutor:
                futuro = ejecutor.submit(recibir)
                try:
                    self.assertTrue(localizado.wait(10))
                    enviar_intento(intento.pk, self.puerto)
                finally:
                    continuar.set()
                self.assertEqual(futuro.result(timeout=10), "pendiente_correlacion")
        with (
            override_settings(PEDIDOS_COBRO_HABILITADO=False),
            patch("ambito.operaciones_cuenta.recuperar_abandonadas"),
            patch("ambito.operaciones_cuenta.ejecutar_pendientes"),
        ):
            ciclo(self.puerto)
            ciclo(self.puerto)
        intento.refresh_from_db()
        self.assertEqual(intento.estado, "pagado")
        self.assertEqual(Movimiento.objects.get(cobro=intento.cobro).estado, "pagado")
        self.assertEqual(EventoPedido.objects.filter(tipo="pago.confirmado").count(), 1)
        self.assertEqual(len(self.puerto.llamadas), 1)

    def test_i2_datepaid_unix_iso_e_ilegible_no_impiden_pago(self):
        from datetime import datetime, timezone

        intento = self.reservar()
        enviar_intento(intento.pk, self.puerto)
        datos = json.loads(self.cuerpo())
        datos["datePaid"] = 1767268800
        respuesta = self.post(json.dumps(datos), "unix")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["estado"], "aplicado")
        intento.refresh_from_db()
        self.assertEqual(intento.estado, "pagado")
        self.assertEqual(
            AvisoRecibido.objects.get(webhook_id="unix").fecha_pago,
            datetime.fromtimestamp(1767268800, tz=timezone.utc),
        )
        for indice, fecha in enumerate(("2026-01-01T12:00:00Z", "ilegible", 10**30)):
            datos["datePaid"] = fecha
            respuesta = self.post(json.dumps(datos), f"fecha-{indice}")
            self.assertEqual(respuesta.status_code, 200)
            recibido = AvisoRecibido.objects.get(webhook_id=f"fecha-{indice}")
            self.assertEqual(recibido.resultado, "duplicado_transaccion")
            if indice == 0:
                self.assertEqual(
                    recibido.fecha_pago, datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
                )
            else:
                self.assertIsNone(recibido.fecha_pago)

    def test_i1_un_aviso_fallido_no_impide_aplicar_el_siguiente(self):
        from pedidos.servicios import pagos
        from pedidos.servicios.despacho import ciclo

        intento = self.reservar()
        primero = self.cuerpo(tx="primero")
        segundo = self.cuerpo(tx="segundo")
        self.post(primero, "primero")
        self.post(segundo, "segundo")
        with patch(
            "pedidos.servicios.pagos.emitir", side_effect=RuntimeError("evento")
        ):
            enviar_intento(intento.pk, self.puerto)
        original = pagos.aplicar_pago

        def aplicar(aviso):
            if aviso.webhook_id == "primero":
                raise RuntimeError("fallo transitorio")
            return original(aviso)

        with (
            override_settings(PEDIDOS_COBRO_HABILITADO=False),
            patch("ambito.operaciones_cuenta.recuperar_abandonadas"),
            patch("ambito.operaciones_cuenta.ejecutar_pendientes"),
            patch("pedidos.servicios.pagos.aplicar_pago", side_effect=aplicar),
            self.assertLogs("pedidos.servicios.pagos", level="WARNING"),
        ):
            ciclo(self.puerto)
        intento.refresh_from_db()
        self.assertEqual(intento.estado, "pagado")
        self.assertEqual(
            AvisoRecibido.objects.get(webhook_id="primero").correlacion, "pendiente"
        )
        self.assertEqual(
            AvisoRecibido.objects.get(webhook_id="segundo").resultado, "aplicado"
        )
        self.assertEqual(EventoPedido.objects.filter(tipo="pago.confirmado").count(), 1)

    def test_i2_notificacion_acepta_unix_y_activacion_de_cuenta_no_cambia(self):
        from datetime import datetime, timezone

        resultado = self.nucleo.solicitar_cobro(
            self.ctx,
            contrato_version="1.0",
            command_key="notificacion",
            pedido_id=self.pedido.id,
            expected_version=self.pedido.version,
            aceptacion_id=self.pedido.aceptacion.id,
            canal="notificacion",
            telefono_bancario_confirmado="1234567890",
        )
        self.assertTrue(resultado.ok, resultado.error)
        intento = IntentoCobro.objects.get(pedido_id=self.pedido.id)
        enviar_intento(intento.pk, self.puerto)
        intento.refresh_from_db()
        cuerpo = json.dumps(
            {
                "type": "codi.pn.payment_received",
                "amount": 25,
                "transactionId": intento.cobro.pey_transaction_id,
                "bankAccountId": intento.pey_bank_account_id,
                "datePaid": 1767268800,
            },
            separators=(",", ":"),
        )
        respuesta = self.post(cuerpo, "pn-unix")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["estado"], "aplicado")
        self.assertEqual(
            AvisoRecibido.objects.get(webhook_id="pn-unix").fecha_pago,
            datetime.fromtimestamp(1767268800, tz=timezone.utc),
        )
        intento.refresh_from_db()
        self.assertEqual(intento.estado, "pagado")
        cuenta = json.dumps(
            {
                "type": "bank.account.updated",
                "codiStatus": "ACTIVE",
                "bankAccountId": self.cuenta.pey_bank_account_id,
                "datePaid": 1767268800,
            },
            separators=(",", ":"),
        )
        with patch("webhooks.views.encolar_sync") as encolar:
            respuesta = self.post(cuenta, "activacion-unix")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["estado"], "aplicado")
        encolar.assert_called_once()

    def test_i2_payload_pey_de_un_centavo_confirma_venta_legacy(self):
        from decimal import Decimal

        from movimientos.models import Cobro

        cobro = Cobro.objects.create(
            comercio=self.comercio,
            cuenta=self.cuenta,
            canal="qr_venta",
            monto=Decimal("0.01"),
            concepto="Venta",
            pey_qr_id="qr-un-centavo",
            qr_string="qr",
            pey_bank_account_id=self.cuenta.pey_bank_account_id,
        )
        movimiento = Movimiento.objects.create(
            comercio=self.comercio,
            cobro=cobro,
            canal="qr_venta",
            monto=Decimal("0.01"),
            concepto="Venta",
            origen="origen_pey",
        )
        cuerpo = json.dumps(
            {
                "type": "codi.qr.payment_received",
                "amount": 0.01,
                "transactionId": "01ARZ3NDEKTSV4RRFFQ69G5FAW",
                "codiQrId": cobro.pey_qr_id,
                "bankAccountId": cobro.pey_bank_account_id,
                "datePaid": 1767268800,
            },
            separators=(",", ":"),
        )
        respuesta = self.post(cuerpo, "centavo-unix")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["estado"], "aplicado")
        movimiento.refresh_from_db()
        self.assertEqual(movimiento.estado, "pagado")
        self.assertIsNotNone(AvisoRecibido.objects.get(webhook_id="centavo-unix").fecha_pago)
