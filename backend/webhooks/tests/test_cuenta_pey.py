"""Avisos de activación firmados sin consultas a pey durante el acuse."""

import json
from unittest.mock import patch

from django.test import TestCase, override_settings

from ambito.models import Comercio, OperacionCuenta
from ambito.tests.soporte import crear_cuenta
from webhooks.models import AvisoRecibido
from webhooks.tests.support.pey_webhook import SECRETO, post_firmado


def _cuerpo(identificador: str) -> str:
    return json.dumps({
        "type": "bank.account.updated", "bankAccountId": identificador,
        "codiStatus": "ACTIVE",
    })


@override_settings(PEY_WEBHOOK_SECRET=SECRETO)
class AvisoCuentaPeyTests(TestCase):
    def setUp(self) -> None:
        self.comercio = Comercio.objects.create(nombre="Por activar")
        self.cuenta = crear_cuenta(
            self.comercio, estado="pending", predeterminada=False
        )

    def test_webhook_activacion_encola_y_no_hace_get_en_el_acuse(self) -> None:
        cuerpo = _cuerpo(self.cuenta.pey_bank_account_id)
        with patch(
            "ambito.operaciones_cuenta.consultar_cuenta", side_effect=AssertionError
        ):
            respuesta = post_firmado(self.client, cuerpo, "msg_cuenta_ok")
            repetido = post_firmado(self.client, cuerpo, "msg_cuenta_ok")
            otro = post_firmado(self.client, cuerpo, "msg_cuenta_otro")
        self.assertEqual(respuesta.json(), {"estado": "aplicado"})
        self.assertEqual(repetido.json(), {"estado": "duplicado"})
        self.assertEqual(otro.json(), {"estado": "aplicado"})
        self.assertEqual(OperacionCuenta.objects.filter(
            cuenta=self.cuenta, tipo="sync", estado="pendiente"
        ).count(), 1)
        self.cuenta.refresh_from_db()
        self.assertEqual(self.cuenta.codi_status, "pending")

    def test_id_desconocido_no_encola(self) -> None:
        respuesta = post_firmado(
            self.client, _cuerpo("01J9ZQ4C8X7Y6W5V4T3S2R1Q0N"), "ajeno"
        )
        self.assertEqual(respuesta.json(), {"estado": "sin_cobro"})
        self.assertFalse(OperacionCuenta.objects.exists())

    def test_firma_invalida_no_cambia_nada(self) -> None:
        respuesta = self.client.post(
            "/api/webhooks/pey/", data=_cuerpo(self.cuenta.pey_bank_account_id),
            content_type="application/json",
            headers={"webhook-id": "mala", "webhook-signature": "v1,mala"},
        )
        self.assertEqual(respuesta.status_code, 401)
        self.assertFalse(AvisoRecibido.objects.exists())
        self.assertFalse(OperacionCuenta.objects.exists())
