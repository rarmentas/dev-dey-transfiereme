"""Aceptación historia 2.2: aviso QR general por POST /api/webhooks/pey/."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from ambito.models import Comercio, Membresia
from movimientos.models import Cobro, Movimiento
from webhooks.models import AvisoRecibido
from webhooks.tests.support.pey_webhook import (
    SECRETO,
    cuerpo_qr,
    post_firmado,
)


def _cobro_qr_general(comercio: Comercio, pey_qr_id: str) -> Cobro:
    return Cobro.objects.create(
        comercio=comercio,
        canal=Movimiento.Canal.QR_GENERAL,
        monto=Decimal("0.00"),
        concepto="Transferencia",
        pey_qr_id=pey_qr_id,
        qr_string=f"qr-test-general-{pey_qr_id}",
    )


@override_settings(PEY_WEBHOOK_SECRET=SECRETO)
class RutaQrGeneralTests(TestCase):
    def setUp(self) -> None:
        self.cliente_webhook = APIClient()
        self.cliente_api = APIClient()
        self.comercio = Comercio.objects.create(nombre="Local demo")

    def test_primer_aviso_marca_pagado_una_vez(self) -> None:
        cobro = _cobro_qr_general(self.comercio, "QR-GEN-UNO")
        cuerpo = cuerpo_qr(
            transaction_id="TX-PRIMERO",
            codi_qr_id="QR-GEN-UNO",
            amount=0.01,
        )
        respuesta = post_firmado(self.cliente_webhook, cuerpo, "msg_h2_primer_aviso")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json(), {"estado": "aplicado"})
        self.assertEqual(cobro.movimientos.count(), 1)
        movimiento = cobro.movimientos.get()
        self.assertEqual(movimiento.estado, Movimiento.Estado.PAGADO)
        self.assertEqual(movimiento.origen, Movimiento.Origen.ORIGEN_PEY)
        self.assertEqual(movimiento.canal, Movimiento.Canal.QR_GENERAL)
        self.assertEqual(movimiento.monto, Decimal("0.01"))
        self.assertEqual(movimiento.pey_transaction_id, "TX-PRIMERO")
        self.assertEqual(movimiento.comercio_id, self.comercio.pk)

        aviso = AvisoRecibido.objects.get(webhook_id="msg_h2_primer_aviso")
        self.assertEqual(aviso.resultado, AvisoRecibido.Resultado.APLICADO)
        self.assertEqual(aviso.movimiento_id, movimiento.pk)
        self.assertEqual(aviso.tipo, "codi.qr.payment_received")

    def test_transaction_id_repetido_sin_segundo_movimiento(self) -> None:
        cobro = _cobro_qr_general(self.comercio, "QR-GEN-IDEM")
        cuerpo = cuerpo_qr(
            transaction_id="TX-REPETIDO-H2",
            codi_qr_id="QR-GEN-IDEM",
            amount=0.01,
        )
        primera = post_firmado(self.cliente_webhook, cuerpo, "msg_h2_tx_uno")
        segunda = post_firmado(self.cliente_webhook, cuerpo, "msg_h2_tx_dos")
        self.assertEqual(primera.json(), {"estado": "aplicado"})
        self.assertEqual(segunda.status_code, 200)
        self.assertEqual(segunda.json(), {"estado": "duplicado_transaccion"})
        self.assertEqual(cobro.movimientos.count(), 1)
        self.assertEqual(AvisoRecibido.objects.count(), 2)
        self.assertEqual(
            AvisoRecibido.objects.get(webhook_id="msg_h2_tx_dos").resultado,
            AvisoRecibido.Resultado.DUPLICADO_TRANSACCION,
        )

    def test_aviso_solo_actualiza_comercio_del_cobro_con_sesion_ajena(
        self,
    ) -> None:
        comercio_a = Comercio.objects.create(nombre="Comercio A")
        comercio_b = Comercio.objects.create(nombre="Comercio B")
        _cobro_qr_general(comercio_a, "QR-GEN-A")
        cobro_b = _cobro_qr_general(comercio_b, "QR-GEN-B")

        usuario_a = User.objects.create_user(username="vendedor_a_h2", password="pass-a")
        usuario_b = User.objects.create_user(username="vendedor_b_h2", password="pass-b")
        Membresia.objects.create(usuario=usuario_a, comercio=comercio_a)
        Membresia.objects.create(usuario=usuario_b, comercio=comercio_b)

        self.cliente_api.force_login(usuario_a)

        cuerpo = cuerpo_qr(
            transaction_id="TX-COMERCIO-B",
            codi_qr_id="QR-GEN-B",
            amount=0.01,
        )
        respuesta = post_firmado(self.cliente_webhook, cuerpo, "msg_h2_r7")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json(), {"estado": "aplicado"})

        movimiento_b = cobro_b.movimientos.get()
        self.assertEqual(comercio_b.movimientos.count(), 1)
        self.assertFalse(comercio_a.movimientos.exists())

        listado_a = self.cliente_api.get("/api/movimientos/")
        self.assertEqual(listado_a.status_code, 200)
        ids_a = [item["id"] for item in listado_a.json()]
        self.assertNotIn(movimiento_b.pk, ids_a)

        self.cliente_api.force_login(usuario_b)
        listado_b = self.cliente_api.get("/api/movimientos/")
        self.assertEqual(listado_b.status_code, 200)
        ids_b = [item["id"] for item in listado_b.json()]
        self.assertIn(movimiento_b.pk, ids_b)
        pagado = next(item for item in listado_b.json() if item["id"] == movimiento_b.pk)
        self.assertEqual(pagado["estado"], Movimiento.Estado.PAGADO)
        self.assertEqual(pagado["canal"], Movimiento.Canal.QR_GENERAL)
