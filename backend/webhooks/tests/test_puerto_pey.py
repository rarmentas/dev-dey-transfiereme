import base64
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from math import floor

from django.test import TestCase, override_settings
from standardwebhooks import Webhook

from ambito.models import Comercio
from movimientos.models import Cobro, Movimiento
from webhooks.models import AvisoRecibido

SECRETO = "whsec_" + base64.b64encode(
    b"prueba-historia-1.5-no-es-secreto-real"
).decode()

RUTA = "/api/webhooks/pey/"


def _encabezados(cuerpo: str, msg_id: str, cuando: datetime) -> dict[str, str]:
    firma = Webhook(SECRETO).sign(msg_id, cuando, cuerpo)
    marca = str(floor(cuando.replace(tzinfo=timezone.utc).timestamp()))
    return {
        "webhook-id": msg_id,
        "webhook-timestamp": marca,
        "webhook-signature": firma,
    }


def _cuerpo_qr(
    *,
    transaction_id: str,
    codi_qr_id: str,
    amount: object = 25,
) -> str:
    return json.dumps(
        {
            "type": "codi.qr.payment_received",
            "amount": amount,
            "concept": "Transferencia",
            "transactionId": transaction_id,
            "codiQrId": codi_qr_id,
        },
        separators=(",", ":"),
    )


@override_settings(PEY_WEBHOOK_SECRET=SECRETO)
class PuertoWebhookPeyTests(TestCase):
    def setUp(self) -> None:
        self.comercio = Comercio.objects.create(nombre="Abarrotes Centro")

    def _post(
        self,
        cuerpo: str,
        msg_id: str,
        *,
        cuando: datetime | None = None,
        headers: dict[str, str] | None = None,
    ):
        cuando = cuando or datetime.now(timezone.utc)
        if headers is None:
            headers = _encabezados(cuerpo, msg_id, cuando)
        return self.client.post(
            RUTA,
            data=cuerpo,
            content_type="application/json",
            headers=headers,
        )

    def _qr_venta(self, pey_qr_id: str) -> Movimiento:
        cobro = Cobro.objects.create(
            comercio=self.comercio,
            canal=Movimiento.Canal.QR_VENTA,
            monto=Decimal("25.00"),
            concepto="Transferencia",
            pey_qr_id=pey_qr_id,
        )
        return Movimiento.objects.create(
            comercio=self.comercio,
            cobro=cobro,
            monto=Decimal("25.00"),
            concepto="Transferencia",
            canal=Movimiento.Canal.QR_VENTA,
            origen=Movimiento.Origen.ORIGEN_PEY,
        )

    def _qr_general(self, pey_qr_id: str) -> Cobro:
        return Cobro.objects.create(
            comercio=self.comercio,
            canal=Movimiento.Canal.QR_GENERAL,
            monto=Decimal("0.00"),
            concepto="Transferencia",
            pey_qr_id=pey_qr_id,
        )

    def test_firma_invalida_no_escribe_ni_marca_pagado(self) -> None:
        movimiento = self._qr_venta("QR-VENTA")
        cuerpo = _cuerpo_qr(transaction_id="TX-VENTA", codi_qr_id="QR-VENTA")
        ahora = datetime.now(timezone.utc)
        validos = _encabezados(cuerpo, "msg_firma", ahora)
        firma_mala = dict(validos)
        firma_mala["webhook-signature"] = "v1," + base64.b64encode(
            b"firma-incorrecta"
        ).decode()
        sin_firma = {
            "webhook-id": "msg_firma",
            "webhook-timestamp": validos["webhook-timestamp"],
        }
        casos = (
            ("firma", firma_mala),
            ("sin_headers", {}),
            ("header_ausente", sin_firma),
            ("timestamp_viejo", _encabezados(cuerpo, "msg_viejo", ahora - timedelta(minutes=6))),
        )
        for nombre, headers in casos:
            with self.subTest(nombre=nombre):
                respuesta = self._post(cuerpo, "msg_firma", headers=headers)
                self.assertEqual(respuesta.status_code, 401)
                self.assertEqual(respuesta.json(), {"detalle": "firma inválida"})

        self.assertEqual(AvisoRecibido.objects.count(), 0)
        leido = Movimiento.objects.get(pk=movimiento.pk)
        self.assertEqual(leido.estado, Movimiento.Estado.PENDIENTE)
        self.assertIsNone(leido.pey_transaction_id)

    @override_settings(PEY_WEBHOOK_SECRET="")
    def test_secreto_vacio_rechaza_aunque_la_firma_parezca_valida(self) -> None:
        movimiento = self._qr_venta("QR-VENTA")
        cuerpo = _cuerpo_qr(transaction_id="TX-VENTA", codi_qr_id="QR-VENTA")
        respuesta = self._post(cuerpo, "msg_vacio")
        self.assertEqual(respuesta.status_code, 401)
        self.assertEqual(respuesta.json(), {"detalle": "firma inválida"})
        self.assertEqual(AvisoRecibido.objects.count(), 0)
        self.assertEqual(
            Movimiento.objects.get(pk=movimiento.pk).estado,
            Movimiento.Estado.PENDIENTE,
        )

    def test_aviso_qr_venta_marca_pagado_con_origen_pey(self) -> None:
        movimiento = self._qr_venta("QR-VENTA")
        cuerpo = _cuerpo_qr(transaction_id="TX-VENTA", codi_qr_id="QR-VENTA")
        respuesta = self._post(cuerpo, "msg_venta")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json(), {"estado": "aplicado"})

        leido = Movimiento.objects.get(pk=movimiento.pk)
        self.assertEqual(leido.estado, Movimiento.Estado.PAGADO)
        self.assertEqual(leido.origen, Movimiento.Origen.ORIGEN_PEY)
        self.assertEqual(leido.pey_transaction_id, "TX-VENTA")

        aviso = AvisoRecibido.objects.get(webhook_id="msg_venta")
        self.assertEqual(aviso.resultado, AvisoRecibido.Resultado.APLICADO)
        self.assertEqual(aviso.movimiento_id, movimiento.pk)
        self.assertEqual(aviso.tipo, "codi.qr.payment_received")

    def test_aviso_qr_general_guarda_un_centavo(self) -> None:
        cobro = self._qr_general("QR-GEN")
        cuerpo = (
            '{"type":"codi.qr.payment_received","amount":0.01,'
            '"concept":"Transferencia","transactionId":"TX-CENTAVO",'
            '"codiQrId":"QR-GEN"}'
        )
        respuesta = self._post(cuerpo, "msg_centavo")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json(), {"estado": "aplicado"})
        self.assertEqual(cobro.movimientos.count(), 1)
        movimiento = cobro.movimientos.get()
        self.assertEqual(movimiento.monto, Decimal("0.01"))
        self.assertIsInstance(movimiento.monto, Decimal)
        self.assertEqual(movimiento.estado, Movimiento.Estado.PAGADO)
        self.assertEqual(movimiento.origen, Movimiento.Origen.ORIGEN_PEY)
        self.assertEqual(movimiento.canal, Movimiento.Canal.QR_GENERAL)

    def test_el_mismo_webhook_id_no_aplica_el_monto_dos_veces(self) -> None:
        cobro = self._qr_general("QR-GEN")
        cuerpo = (
            '{"type":"codi.qr.payment_received","amount":0.01,'
            '"concept":"Transferencia","transactionId":"TX-UNICO",'
            '"codiQrId":"QR-GEN"}'
        )
        primera = self._post(cuerpo, "msg_repetido")
        segunda = self._post(cuerpo, "msg_repetido")
        self.assertEqual(primera.status_code, 200)
        self.assertEqual(primera.json(), {"estado": "aplicado"})
        self.assertEqual(segunda.status_code, 200)
        self.assertEqual(segunda.json(), {"estado": "duplicado"})
        self.assertEqual(cobro.movimientos.count(), 1)
        total = sum((mov.monto for mov in cobro.movimientos.all()), Decimal("0"))
        self.assertEqual(total, Decimal("0.01"))
        self.assertEqual(AvisoRecibido.objects.count(), 1)

    def test_otro_webhook_con_el_mismo_transaction_id_no_crea_otro_movimiento(
        self,
    ) -> None:
        cobro = self._qr_general("QR-GEN")
        cuerpo = (
            '{"type":"codi.qr.payment_received","amount":0.01,'
            '"concept":"Transferencia","transactionId":"TX-REPETIDO",'
            '"codiQrId":"QR-GEN"}'
        )
        primera = self._post(cuerpo, "msg_uno")
        segunda = self._post(cuerpo, "msg_dos")
        self.assertEqual(primera.json(), {"estado": "aplicado"})
        self.assertEqual(segunda.status_code, 200)
        self.assertEqual(segunda.json(), {"estado": "duplicado_transaccion"})
        self.assertEqual(cobro.movimientos.count(), 1)
        self.assertEqual(
            AvisoRecibido.objects.get(webhook_id="msg_dos").resultado,
            AvisoRecibido.Resultado.DUPLICADO_TRANSACCION,
        )
        total = sum((mov.monto for mov in cobro.movimientos.all()), Decimal("0"))
        self.assertEqual(total, Decimal("0.01"))

    def test_aviso_pn_marca_la_notificacion_pagada(self) -> None:
        cobro = Cobro.objects.create(
            comercio=self.comercio,
            canal=Movimiento.Canal.NOTIFICACION,
            monto=Decimal("25.00"),
            concepto="Transferencia",
            pey_transaction_id="TX-PN",
        )
        movimiento = Movimiento.objects.create(
            comercio=self.comercio,
            cobro=cobro,
            monto=Decimal("25.00"),
            concepto="Transferencia",
            canal=Movimiento.Canal.NOTIFICACION,
            origen=Movimiento.Origen.ORIGEN_PEY,
        )
        cuerpo = json.dumps(
            {
                "type": "codi.pn.payment_received",
                "amount": 25,
                "concept": "Transferencia",
                "transactionId": "TX-PN",
            },
            separators=(",", ":"),
        )
        respuesta = self._post(cuerpo, "msg_pn")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json(), {"estado": "aplicado"})
        leido = Movimiento.objects.get(pk=movimiento.pk)
        self.assertEqual(leido.estado, Movimiento.Estado.PAGADO)
        self.assertEqual(leido.canal, Movimiento.Canal.NOTIFICACION)
        self.assertEqual(leido.pey_transaction_id, "TX-PN")
        self.assertEqual(leido.origen, Movimiento.Origen.ORIGEN_PEY)

    def test_cobro_inexistente_responde_sin_cobro(self) -> None:
        cuerpo = _cuerpo_qr(transaction_id="TX-NADIE", codi_qr_id="QR-NADIE")
        respuesta = self._post(cuerpo, "msg_nadie")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json(), {"estado": "sin_cobro"})
        self.assertEqual(Movimiento.objects.count(), 0)
        self.assertEqual(
            AvisoRecibido.objects.get().resultado,
            AvisoRecibido.Resultado.SIN_COBRO,
        )

    def test_aviso_sobre_vencido_sigue_vencido(self) -> None:
        movimiento = self._qr_venta("QR-VENCIDO")
        movimiento.cambiar_estado(Movimiento.Estado.VENCIDO)
        cuerpo = _cuerpo_qr(transaction_id="TX-TARDE", codi_qr_id="QR-VENCIDO")
        respuesta = self._post(cuerpo, "msg_tarde")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json(), {"estado": "transicion_invalida"})
        leido = Movimiento.objects.get(pk=movimiento.pk)
        self.assertEqual(leido.estado, Movimiento.Estado.VENCIDO)
        self.assertIsNone(leido.pey_transaction_id)
        self.assertEqual(
            AvisoRecibido.objects.get().resultado,
            AvisoRecibido.Resultado.TRANSICION_INVALIDA,
        )

    def test_json_invalido_o_sin_transaction_id_no_escribe(self) -> None:
        casos = (
            "no-es-json",
            json.dumps(
                {
                    "type": "codi.qr.payment_received",
                    "amount": 1,
                    "codiQrId": "QR-VENTA",
                },
                separators=(",", ":"),
            ),
        )
        for indice, cuerpo in enumerate(casos):
            with self.subTest(cuerpo=cuerpo):
                respuesta = self._post(cuerpo, f"msg_malo_{indice}")
                self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(AvisoRecibido.objects.count(), 0)

    def test_get_no_esta_permitido(self) -> None:
        respuesta = self.client.get(RUTA)
        self.assertEqual(respuesta.status_code, 405)
        self.assertEqual(AvisoRecibido.objects.count(), 0)
