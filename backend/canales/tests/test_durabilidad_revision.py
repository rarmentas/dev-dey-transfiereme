"""Pruebas transaccionales del receptor de WAHA."""

import hashlib
import hmac
import json
import threading
from unittest.mock import patch

from django.db import OperationalError, close_old_connections, connection
from django.test import Client, TransactionTestCase, override_settings

from ambito.models import Comercio
from canales.models import MensajeEntrante, SesionCanal


@override_settings(WAHA_WEBHOOK_SECRET="prueba", WAHA_INSTANCIA="waha")
class DurabilidadRevisionTests(TransactionTestCase):
    def setUp(self):
        self.comercio = Comercio.objects.create(nombre="Tienda")
        SesionCanal.objects.create(
            instancia_id="waha", sesion_id="s", comercio=self.comercio
        )
        self.cuerpo = json.dumps(
            {
                "event": "message",
                "session": "s",
                "payload": {
                    "id": "m1",
                    "from": "cliente@c.us",
                    "fromMe": False,
                    "body": "leche",
                },
            }
        ).encode()
        self.firma = hmac.new(b"prueba", self.cuerpo, hashlib.sha512).hexdigest()

    def post(self):
        return Client().post(
            "/api/webhooks/waha/",
            data=self.cuerpo,
            content_type="application/json",
            HTTP_X_WEBHOOK_HMAC=self.firma,
            HTTP_X_WEBHOOK_HMAC_ALGORITHM="sha512",
        )

    def test_i8_webhook_simultaneo_una_entrada(self):
        barrera = threading.Barrier(2)
        estados = []
        errores = []

        def ejecutar():
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                estados.append(self.post().json()["estado"])
            except Exception as exc:
                errores.append(exc)
            finally:
                connection.close()

        hilos = [threading.Thread(target=ejecutar) for _ in range(2)]
        for hilo in hilos:
            hilo.start()
        for hilo in hilos:
            hilo.join(timeout=15)
        self.assertFalse(any(hilo.is_alive() for hilo in hilos))
        self.assertEqual(errores, [])
        self.assertCountEqual(estados, ["recibido", "duplicado"])
        self.assertEqual(
            list(MensajeEntrante.objects.values_list("secuencia", flat=True)), [1]
        )

    def test_i8_acuse_solo_despues_commit(self):
        from django.http import JsonResponse

        observado = []

        def respuesta(*args, **kwargs):
            observado.append(
                (connection.in_atomic_block, MensajeEntrante.objects.count())
            )
            return JsonResponse(*args, **kwargs)

        with patch("canales.views.JsonResponse", side_effect=respuesta):
            self.assertEqual(self.post().status_code, 200)
        self.assertEqual(observado, [(False, 1)])

    def test_i8_base_caida_es_503(self):
        with patch("canales.views.recibir", side_effect=OperationalError):
            self.assertEqual(self.post().status_code, 503)
        self.assertFalse(MensajeEntrante.objects.exists())

    @override_settings(WAHA_WEBHOOK_SECRET="")
    def test_i8_sin_secreto_rechaza(self):
        self.assertEqual(self.post().status_code, 401)
        self.assertFalse(MensajeEntrante.objects.exists())

    def test_i3_instancia_waha_provisionada_recibe(self):
        self.assertEqual(self.post().json()["estado"], "recibido")
        self.assertEqual(MensajeEntrante.objects.count(), 1)
