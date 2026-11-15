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

    def test_i8_cuenta_inactiva_ambas_rutas_incluyen_codigo(self):
        self.comercio.cuenta_por_defecto = None
        self.comercio.save(update_fields=["cuenta_por_defecto"])
        casos = (
            ("/api/ventas/", {"monto": "25.00"}),
            ("/api/ventas/notificacion/", {"monto": "25.00", "telefono": "1234567890"}),
        )
        for ruta, datos in casos:
            with self.subTest(ruta=ruta):
                respuesta = self.cliente.post(
                    ruta, datos, format="json", HTTP_IDEMPOTENCY_KEY="clave-i8"
                )
                self.assertEqual(respuesta.status_code, 409)
                self.assertEqual(respuesta.json()["codigo"], "CUENTA_NO_ACTIVE")
                self.assertEqual(
                    respuesta.json()["detail"], "La cuenta no está ACTIVE."
                )
        self.assertFalse(IntentoCobro.objects.exists())

    def test_otro_comercio_demo_no_bloquea_venta_normal(self):
        Comercio.objects.create(nombre="Demo", es_demo=True)
        respuesta = self.post("normal")
        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        intento = IntentoCobro.objects.get(comercio=self.comercio)
        self.assertFalse(intento.demo_mode)
        self.assertEqual(intento.politica_cobro_version, "normal-1")
        self.assertEqual(intento.importe_efectivo_centavos, 2500)
        self.assertEqual(intento.cuenta_id, self.comercio.cuenta_por_defecto_id)
        self.assertEqual(
            self.puerto.llamadas[0][1]["bank_account_id"],
            self.comercio.cuenta_por_defecto.pey_bank_account_id,
        )

    def test_las_tres_rutas_funcionan_para_normal_con_demo_existente(self):
        from decimal import Decimal
        from unittest.mock import Mock

        from movimientos.models import Movimiento
        from pedidos.servicios.cobros import vencer_intento
        from pey.tipos import QrCreado

        Comercio.objects.create(nombre="Demo", es_demo=True)
        cuenta = self.comercio.cuenta_por_defecto
        for ruta, datos in (
            ("/api/ventas/", {"monto": "25.00"}),
            ("/api/ventas/notificacion/", {"monto": "25.00", "telefono": "1234567890"}),
        ):
            with self.subTest(ruta=ruta):
                self.puerto.siguiente_id = "id-" + str(len(self.puerto.llamadas))
                with patch(
                    "pedidos.servicios.despacho.obtener_puerto",
                    return_value=self.puerto,
                ):
                    respuesta = self.cliente.post(
                        ruta, datos, format="json",
                        HTTP_IDEMPOTENCY_KEY="clave-" + str(len(self.puerto.llamadas)),
                    )
                self.assertEqual(respuesta.status_code, 201, respuesta.content)
                self.assertIn("movimiento_id", respuesta.json())
                self.assertEqual(respuesta.json()["monto"], "25.00")
                self.assertEqual(respuesta.json()["estado"], "pendiente")
                if ruta.endswith("notificacion/"):
                    self.assertEqual(respuesta.json()["canal"], "notificacion")
                    self.assertEqual(respuesta.json()["telefono_final"], "7890")
                else:
                    self.assertEqual(respuesta.json()["canal"], "qr_venta")
                    self.assertEqual(respuesta.json()["qr_string"], "qr-prueba")
                intento = IntentoCobro.objects.get(
                    cobro__movimientos__pk=respuesta.json()["movimiento_id"]
                )
                self.assertEqual((intento.demo_mode, intento.importe_efectivo_centavos,
                                  intento.cuenta_id, intento.pey_bank_account_id),
                                 (False, 2500, cuenta.pk, cuenta.pey_bank_account_id))
                self.assertEqual(self.puerto.llamadas[-1][1]["monto"], Decimal("25.00"))
                vencer_intento(Movimiento.objects.get(pk=respuesta.json()["movimiento_id"]))
        from pey.produccion import AdaptadorProduccion

        puerto_qr = Mock(spec=AdaptadorProduccion)
        puerto_qr.crear_qr.return_value = QrCreado("qr-general", "contenido")
        with patch(
            "movimientos.alta_qr_general.obtener_puerto", return_value=puerto_qr
        ):
            respuesta = self.cliente.post("/api/cobro/qr-general/", {}, format="json")
        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        self.assertEqual(respuesta.json()["qr_string"], "contenido")
        self.assertEqual(respuesta.json()["pey_qr_id"], "qr-general")
        puerto_qr.crear_qr.assert_called_once()
        self.assertEqual(
            puerto_qr.crear_qr.call_args.kwargs["bank_account_id"],
            cuenta.pey_bank_account_id,
        )
