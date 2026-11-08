"""Aviso bank.account.updated. Firma de prueba; no hay red."""

import json

from django.test import TestCase, override_settings

from ambito.models import Comercio
from movimientos.models import Movimiento
from webhooks.models import AvisoRecibido
from webhooks.tests.support.pey_webhook import SECRETO, post_firmado

_ID = "01J9ZQ4C8X7Y6W5V4T3S2R1Q0P"


def _cuerpo(bank_account_id: str, codi_status: str = "ACTIVE") -> str:
    return json.dumps(
        {
            "type": "bank.account.updated",
            "bankAccountId": bank_account_id,
            "name": "Ana",
            "ownerType": "API_KEY",
            "ownerId": "01OWNER",
            "codiStatus": codi_status,
            "clabe": "012180015826225713",
            "entity": "PERSON",
        },
        separators=(",", ":"),
    )


@override_settings(PEY_WEBHOOK_SECRET=SECRETO)
class AvisoCuentaPeyTests(TestCase):
    def setUp(self) -> None:
        self.comercio = Comercio.objects.create(
            nombre="Por activar",
            pey_bank_account_id=_ID,
            pey_codi_status=Comercio.PeyCodiStatus.PENDING,
        )

    def test_active_marca_el_comercio_y_el_repetido_es_duplicado(self) -> None:
        cuerpo = _cuerpo(_ID)
        respuesta = post_firmado(self.client, cuerpo, "msg_cuenta_ok")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json(), {"estado": "aplicado"})
        self.comercio.refresh_from_db()
        self.assertEqual(self.comercio.pey_codi_status, Comercio.PeyCodiStatus.ACTIVE)
        self.assertIsNotNone(self.comercio.pey_codi_status_actualizado_en)
        self.assertEqual(Movimiento.objects.count(), 0)

        repetido = post_firmado(self.client, cuerpo, "msg_cuenta_ok")
        self.assertEqual(repetido.status_code, 200)
        self.assertEqual(repetido.json(), {"estado": "duplicado"})
        self.assertEqual(AvisoRecibido.objects.count(), 1)
        self.comercio.refresh_from_db()
        self.assertEqual(self.comercio.pey_codi_status, Comercio.PeyCodiStatus.ACTIVE)

    def test_id_desconocido_responde_200_y_avisa(self) -> None:
        cuerpo = _cuerpo("01J9ZQ4C8X7Y6W5V4T3S2R1Q0N")
        with self.assertLogs("webhooks.views", level="WARNING") as logs:
            respuesta = post_firmado(self.client, cuerpo, "msg_cuenta_nadie")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json(), {"estado": "sin_cobro"})
        aviso = AvisoRecibido.objects.get(webhook_id="msg_cuenta_nadie")
        self.assertEqual(aviso.resultado, AvisoRecibido.Resultado.SIN_COBRO)
        self.comercio.refresh_from_db()
        self.assertEqual(self.comercio.pey_codi_status, Comercio.PeyCodiStatus.PENDING)
        texto = " ".join(logs.output)
        self.assertIn("01J9ZQ4C8X7Y6W5V4T3S2R1Q0N", texto)
        self.assertIn("msg_cuenta_nadie", texto)
        self.assertEqual(Movimiento.objects.count(), 0)

    def test_firma_invalida_no_cambia_nada(self) -> None:
        cuerpo = _cuerpo(_ID)
        respuesta = self.client.post(
            "/api/webhooks/pey/",
            data=cuerpo,
            content_type="application/json",
            headers={"webhook-id": "msg_mala", "webhook-signature": "v1,mala"},
        )
        self.assertEqual(respuesta.status_code, 401)
        self.comercio.refresh_from_db()
        self.assertEqual(self.comercio.pey_codi_status, Comercio.PeyCodiStatus.PENDING)
        self.assertIsNone(self.comercio.pey_codi_status_actualizado_en)
        self.assertEqual(AvisoRecibido.objects.count(), 0)
