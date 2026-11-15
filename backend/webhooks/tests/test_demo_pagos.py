"""Los pagos conservan su importe y destino históricos, incluso en demo."""

from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import Client, override_settings

from ambito.models import Comercio
from ambito.tests.soporte import crear_cuenta
from movimientos.models import Cobro
from pedidos.models import EventoPedido
from pedidos.servicios.despacho import enviar_intento
from pedidos.tests.soporte_cobro import PuertoPeyFalso
from pedidos.tests.soporte_real import CasoReal
from webhooks.tests import test_inbox_pago
from webhooks.tests.support.pey_webhook import SECRETO

DESTINO = "01ARZ3NDEKTSV4RRFFQ69G5FAV"


@override_settings(
    PEDIDOS_COBRO_HABILITADO=True,
    PEY_WEBHOOK_SECRET=SECRETO,
    DEMO_PEY_BANK_ACCOUNT_ID=DESTINO,
)
class DemoPagosTests(CasoReal):
    reservar = test_inbox_pago.InboxPagoTests.reservar
    cuerpo = test_inbox_pago.InboxPagoTests.cuerpo
    post = test_inbox_pago.InboxPagoTests.post

    def test_qr_general_en_demo_acredita_a_la_cuenta_real(self):
        comercio = Comercio.objects.create(nombre="Comercio con QR")
        cuenta = crear_cuenta(comercio)
        cobro = Cobro.objects.create(
            comercio=comercio,
            cuenta=cuenta,
            canal="qr_general",
            monto=0,
            concepto="Transferencia",
            qr_string="qr",
            pey_qr_id="qr-general-demo",
            pey_bank_account_id=cuenta.pey_bank_account_id,
        )
        call_command(
            "designar_comercio_demo",
            "--comercio",
            str(comercio.pk),
            "--si",
            stdout=StringIO(),
            stderr=StringIO(),
        )
        comercio.refresh_from_db()
        self.assertTrue(comercio.es_demo)
        self.cliente = Client()
        self.cuenta = cuenta
        respuesta = self.post(
            self.cuerpo(qr=cobro.pey_qr_id, monto=25, banco=DESTINO, tx="ajeno"),
            "qr-demo-destino-ajeno",
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["estado"], "destino_distinto")
        self.assertFalse(cobro.movimientos.exists())
        respuesta = self.post(
            self.cuerpo(qr=cobro.pey_qr_id, monto=25, tx="pago-real"),
            "qr-demo-pago-real",
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["estado"], "aplicado")
        movimiento = cobro.movimientos.get()
        self.assertEqual(movimiento.comercio_id, comercio.pk)
        self.assertEqual(movimiento.estado, "pagado")
        self.assertEqual(movimiento.monto, Decimal("25.00"))
        self.assertEqual(movimiento.pey_transaction_id, "pago-real")
        cobro.refresh_from_db()
        self.assertEqual(cobro.pey_bank_account_id, cuenta.pey_bank_account_id)
        self.assertEqual(cobro.cuenta_id, cuenta.pk)
        self.assertNotEqual(cobro.pey_bank_account_id, DESTINO)
        self.assertFalse(EventoPedido.objects.filter(tipo="pago.confirmado").exists())

    def test_pago_exige_importe_y_destino_originales(self):
        self.driver.cambiar_modo(True, "demo-1")
        self.ctx, _, pedido = self.crear()
        pedido = self.cotizar(self.ctx, pedido)
        self.pedido = self.nucleo.aceptar_cotizacion(
            self.ctx, **self.datos_aceptacion(self.ctx, pedido)
        ).data["pedido"]
        self.cliente = Client()
        intento = self.reservar()
        enviar_intento(intento.pk, PuertoPeyFalso())
        self.assertEqual(
            self.post(self.cuerpo(monto=25, banco=DESTINO), "monto").json()["estado"],
            "monto_distinto",
        )
        self.assertEqual(
            self.post(
                self.cuerpo(monto=0.01, banco="01ARZ3NDEKTSV4RRFFQ69G5FAW"), "destino"
            ).json()["estado"],
            "destino_distinto",
        )
        intento.refresh_from_db()
        self.assertEqual(intento.estado, "pendiente")
        self.assertEqual(
            self.post(self.cuerpo(monto=0.01, banco=DESTINO), "correcto").json()[
                "estado"
            ],
            "aplicado",
        )
        intento.refresh_from_db()
        self.assertEqual(intento.estado, "pagado")
        self.assertEqual(EventoPedido.objects.filter(tipo="pago.confirmado").count(), 1)

    def test_cambio_modo_conserva_estados_y_webhook_original(self):
        from ambito.models import Comercio
        from movimientos.models import Movimiento
        from pedidos.models import IntentoCobro

        self.driver.cambiar_modo(True, "demo-1")
        self.ctx, _, pedido = self.crear()
        pedido = self.cotizar(self.ctx, pedido)
        self.pedido = self.nucleo.aceptar_cotizacion(
            self.ctx, **self.datos_aceptacion(self.ctx, pedido)
        ).data["pedido"]
        self.cliente = Client()
        intento = self.reservar()
        puerto = PuertoPeyFalso()
        enviar_intento(intento.pk, puerto)
        intento.refresh_from_db()
        Comercio.objects.filter(pk=intento.comercio_id).update(es_demo=False)
        original = (1, DESTINO, True, "demo-1", None)
        for estado in ("enviando", "pendiente", "incierto", "pagado"):
            with self.subTest(estado=estado):
                IntentoCobro.objects.filter(pk=intento.pk).update(estado=estado)
                Comercio.objects.filter(pk=intento.comercio_id).update(es_demo=True)
                Comercio.objects.filter(pk=intento.comercio_id).update(es_demo=False)
                intento.refresh_from_db()
                self.assertEqual(intento.estado, estado)
                resultado = enviar_intento(intento.pk, puerto)
                self.assertEqual(resultado.estado, estado)
                self.assertEqual(
                    (
                        resultado.importe_efectivo_centavos,
                        resultado.pey_bank_account_id,
                        resultado.demo_mode,
                        resultado.politica_cobro_version,
                        resultado.cuenta_id,
                    ),
                    original,
                )
                self.assertEqual(len(puerto.llamadas), 1)
        IntentoCobro.objects.filter(pk=intento.pk).update(estado="pendiente")
        self.assertEqual(
            self.post(self.cuerpo(monto=25, banco=DESTINO), "monto-flip").json()[
                "estado"
            ],
            "monto_distinto",
        )
        self.assertEqual(
            self.post(
                self.cuerpo(monto=0.01, banco="01ARZ3NDEKTSV4RRFFQ69G5FAW"),
                "destino-flip",
            ).json()["estado"],
            "destino_distinto",
        )
        self.assertEqual(
            self.post(self.cuerpo(monto=0.01, banco=DESTINO), "pago-flip").json()[
                "estado"
            ],
            "aplicado",
        )
        intento.refresh_from_db()
        self.assertEqual(intento.estado, "pagado")
        self.assertEqual(Movimiento.objects.get(cobro=intento.cobro).estado, "pagado")
