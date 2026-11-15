"""Idempotencia de la fachada síncrona."""

from unittest.mock import patch

from ambito.models import Comercio, Membresia
from ambito.tests.soporte import crear_cuenta
from django.contrib.auth.models import User
from django.test import TransactionTestCase
from pedidos.models import IntentoCobro
from pedidos.tests.soporte_cobro import PuertoPeyFalso
from pey.tipos import ErrorPey
from rest_framework.test import APIClient


class FachadaLegacyTests(TransactionTestCase):
    def setUp(self):
        self.comercio = Comercio.objects.create(nombre="Tienda")
        crear_cuenta(self.comercio)
        usuario = User.objects.create_user(username="tendero")
        Membresia.objects.create(usuario=usuario, comercio=self.comercio)
        self.cliente = APIClient()
        self.cliente.force_login(usuario)
        self.puerto = PuertoPeyFalso()

    def post(self, clave=None, monto="25.00"):
        headers = {"HTTP_IDEMPOTENCY_KEY": clave} if clave else {}
        with patch(
            "pedidos.servicios.despacho.obtener_puerto", return_value=self.puerto
        ):
            return self.cliente.post(
                "/api/ventas/", {"monto": monto}, format="json", **headers
            )

    def test_clave_repite_misma_venta_y_no_reenvia(self):
        primera = self.post("clave")
        segunda = self.post("clave")
        self.assertEqual(primera.status_code, 201, primera.content)
        self.assertEqual(segunda.status_code, 201, segunda.content)
        self.assertEqual(primera.json(), segunda.json())
        self.assertIn("movimiento_id", primera.json())
        self.assertIn("qr_string", primera.json())
        self.assertEqual(len(self.puerto.llamadas), 1)

    def test_replay_conserva_payload_incluso_despues_de_vencer(self):
        from movimientos.models import Movimiento
        from pedidos.servicios.cobros import vencer_intento

        primera = self.post("clave")
        self.assertEqual(primera.status_code, 201)
        movimiento = Movimiento.objects.get(pk=primera.json()["movimiento_id"])
        vencer_intento(movimiento)
        segunda = self.post("clave")
        self.assertEqual(segunda.status_code, 201)
        self.assertEqual(segunda.json(), primera.json())
        movimiento.refresh_from_db()
        self.assertEqual(movimiento.estado, "vencido")
        self.assertEqual(len(self.puerto.llamadas), 1)

    def test_sin_clave_y_misma_clave_con_otra_huella(self):
        self.assertEqual(self.post().status_code, 400)
        invalida = self.post("clave con espacios")
        self.assertEqual(invalida.status_code, 400)
        self.assertEqual(invalida.json()["codigo"], "IDEMPOTENCY_KEY_REQUERIDA")
        self.assertFalse(IntentoCobro.objects.exists())
        self.assertEqual(self.post("clave").status_code, 201)
        resultado = self.post("clave", monto="26.00")
        self.assertEqual(resultado.status_code, 409)
        self.assertEqual(resultado.json()["codigo"], "CLAVE_REUTILIZADA")
        self.assertEqual(len(self.puerto.llamadas), 1)

    def test_timeout_bloquea_y_no_reenvia(self):
        self.puerto.fallar_con = ErrorPey(
            "TIMEOUT", "timeout", puede_haberse_creado=True
        )
        primera = self.post("clave")
        self.assertEqual(primera.status_code, 502)
        self.assertEqual(primera.json()["codigo"], "COBRO_INCIERTO")
        self.assertEqual(IntentoCobro.objects.get().estado, "incierto")
        repetida = self.post("clave")
        self.assertEqual(repetida.status_code, 502)
        self.assertEqual(repetida.json(), primera.json())
        self.assertEqual(self.post("otra").status_code, 409)
        self.assertEqual(len(self.puerto.llamadas), 1)
