"""Aceptación historia 2.3: segundo pago QR general vía webhook desarrollo."""

import json
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from ambito.cuenta_sync import sincronizar_codi_status
from ambito.models import Comercio, Membresia
from movimientos.models import Cobro, Movimiento
from pey.desarrollo import AdaptadorDesarrollo

_RUTA_QR = "/api/cobro/qr-general/"
_RUTA_WEBHOOK = "/api/webhooks/desarrollo/"
_CLABE_VALIDA = "012180015826225713"


def _revienta(*args, **kwargs):
    raise AssertionError("no debe haber red")


def _json_cuerpo(cuerpo: dict) -> str:
    serializable = dict(cuerpo)
    monto = serializable.get("amount")
    if isinstance(monto, Decimal):
        serializable["amount"] = float(monto)
    return json.dumps(serializable, separators=(",", ":"))


def post_desarrollo(cliente: APIClient, cuerpo: dict, webhook_id: str):
    return cliente.post(
        _RUTA_WEBHOOK,
        data=_json_cuerpo(cuerpo),
        content_type="application/json",
        headers={"webhook-id": webhook_id},
    )


@override_settings(DEBUG=True, PEY_ADAPTADOR="desarrollo", PEY_API_KEY="", PEY_WEBHOOK_SECRET="")
class QrGeneralDesarrolloTests(TestCase):
    def setUp(self) -> None:
        self.cliente_api = APIClient()
        self.cliente_webhook = APIClient()
        self.adaptador = AdaptadorDesarrollo()
        self.comercio = Comercio.objects.create(
            nombre="Local desarrollo",
            clabe=_CLABE_VALIDA,
            semilla_active_dev=True,
        )
        sincronizar_codi_status(self.comercio)
        self.usuario = User.objects.create_user(username="vendedor_h3", password="pass")
        Membresia.objects.create(usuario=self.usuario, comercio=self.comercio)
        self.cliente_api.force_login(self.usuario)

    @patch("urllib.request.urlopen", _revienta)
    @patch("socket.socket.connect", _revienta)
    def test_dos_transaction_id_distintos_dos_movimientos_desarrollo(self) -> None:
        alta = self.cliente_api.post(_RUTA_QR, {}, format="json")
        self.assertEqual(alta.status_code, 201)
        pey_qr_id = alta.json()["pey_qr_id"]
        cobro = Cobro.objects.get(comercio=self.comercio)

        cuerpo_a = self.adaptador.cuerpo_aviso_qr_pagado(
            monto=Decimal("0.01"),
            codi_qr_id=pey_qr_id,
            transaction_id="TX-H3-A",
        )
        cuerpo_b = self.adaptador.cuerpo_aviso_qr_pagado(
            monto=Decimal("0.02"),
            codi_qr_id=pey_qr_id,
            transaction_id="TX-H3-B",
        )
        primera = post_desarrollo(self.cliente_webhook, cuerpo_a, "msg_h3_uno")
        segunda = post_desarrollo(self.cliente_webhook, cuerpo_b, "msg_h3_dos")
        self.assertEqual(primera.json(), {"estado": "aplicado"})
        self.assertEqual(segunda.json(), {"estado": "aplicado"})
        self.assertEqual(cobro.movimientos.count(), 2)
        montos = {
            m.pey_transaction_id: m.monto
            for m in cobro.movimientos.order_by("pk")
        }
        self.assertEqual(montos["TX-H3-A"], Decimal("0.01"))
        self.assertEqual(montos["TX-H3-B"], Decimal("0.02"))
        for movimiento in cobro.movimientos.all():
            self.assertEqual(movimiento.estado, Movimiento.Estado.PAGADO)
            self.assertEqual(movimiento.origen, Movimiento.Origen.ORIGEN_DESARROLLO)

        tablero = self.cliente_api.get("/api/movimientos/tablero/")
        self.assertEqual(tablero.status_code, 200)
        cuerpo_tablero = tablero.json()
        self.assertEqual(cuerpo_tablero["confirmado"]["total"], "0.00")
        self.assertEqual(cuerpo_tablero["desarrollo"]["total"], "0.03")
        self.assertEqual(len(cuerpo_tablero["desarrollo"]["filas"]), 1)

        repetido = post_desarrollo(
            self.cliente_webhook,
            cuerpo_b,
            "msg_h3_tx_repetido",
        )
        self.assertEqual(repetido.json(), {"estado": "duplicado_transaccion"})
        self.assertEqual(cobro.movimientos.count(), 2)

    @patch("urllib.request.urlopen", _revienta)
    @patch("socket.socket.connect", _revienta)
    def test_segundo_alta_qr_devuelve_el_mismo_cobro(self) -> None:
        primera = self.cliente_api.post(_RUTA_QR, {}, format="json")
        self.assertEqual(primera.status_code, 201)
        with patch(
            "pey.desarrollo.AdaptadorDesarrollo.crear_qr",
            side_effect=AssertionError("no debe invocarse de nuevo"),
        ):
            segunda = self.cliente_api.post(_RUTA_QR, {}, format="json")
        self.assertEqual(segunda.status_code, 200)
        self.assertEqual(segunda.json()["pey_qr_id"], primera.json()["pey_qr_id"])
        self.assertEqual(Cobro.objects.filter(comercio=self.comercio).count(), 1)


@override_settings(DEBUG=False, PEY_ADAPTADOR="produccion", PEY_API_KEY="llave")
class WebhookDesarrolloInaccesibleTests(TestCase):
    def test_fuera_de_modo_desarrollo_responde_404(self) -> None:
        cliente = APIClient()
        cuerpo = AdaptadorDesarrollo().cuerpo_aviso_qr_pagado(
            monto=Decimal("0.01"),
            codi_qr_id="dev-qr-x",
            transaction_id="TX-404",
        )
        respuesta = post_desarrollo(cliente, cuerpo, "msg_404")
        self.assertEqual(respuesta.status_code, 404)
