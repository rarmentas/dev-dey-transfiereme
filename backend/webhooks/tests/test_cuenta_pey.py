"""Avisos de activación firmados sin consultas a pey durante el acuse."""

import json
from unittest.mock import patch

from django.db import connection
from django.test import TestCase, TransactionTestCase, override_settings

from ambito.models import Comercio, OperacionCuenta
from ambito.operaciones_cuenta import ejecutar_pendientes, sincronizar
from ambito.tests.soporte import crear_cuenta
from pey.cuentas import CuentaPey
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


@override_settings(PEY_WEBHOOK_SECRET=SECRETO)
class ActivacionDuranteSyncTests(TransactionTestCase):
    def test_activacion_durante_get_requiere_consulta_posterior(self) -> None:
        comercio = Comercio.objects.create(nombre="Pendiente")
        cuenta = crear_cuenta(comercio, estado="pending")
        llamadas = []

        def consultar(identificador, **kwargs):
            self.assertFalse(connection.in_atomic_block)
            llamadas.append(identificador)
            if len(llamadas) == 1:
                respuesta = post_firmado(
                    self.client, _cuerpo(identificador), "activacion-durante-get"
                )
                self.assertEqual(respuesta.json()["estado"], "aplicado")
                repetido = post_firmado(
                    self.client, _cuerpo(identificador), "segunda-activacion"
                )
                self.assertEqual(repetido.json()["estado"], "aplicado")
                self.assertEqual(
                    cuenta.operaciones.filter(
                        tipo="sync", estado__in=["pendiente", "en_curso"]
                    ).count(),
                    1,
                )
                self.assertEqual(len(llamadas), 1)
                return CuentaPey(identificador, "PENDING", cuenta.clabe)
            return CuentaPey(identificador, "ACTIVE", cuenta.clabe)

        with patch("ambito.operaciones_cuenta.consultar_cuenta", side_effect=consultar):
            sincronizar(cuenta)
            cuenta.refresh_from_db()
            self.assertEqual(cuenta.codi_status, "pending")
            self.assertEqual(
                cuenta.operaciones.filter(tipo="sync", estado="pendiente").count(), 1
            )
            ejecutar_pendientes()
        cuenta.refresh_from_db()
        self.assertEqual(len(llamadas), 2)
        self.assertEqual(cuenta.codi_status, "active")
        self.assertEqual(
            cuenta.operaciones.filter(tipo="sync", estado="aplicada").count(), 2
        )
        self.assertFalse(
            cuenta.operaciones.filter(
                tipo="sync", estado__in=["pendiente", "en_curso"]
            ).exists()
        )
