"""API del tendero para solicitar y activar un cobro."""

from ambito.models import Membresia
from ambito.tests.soporte import crear_cuenta
from django.contrib.auth.models import User
from django.test import override_settings
from rest_framework.test import APIClient

from pedidos.models import IntentoCobro
from pedidos.tests.soporte_real import CasoReal


@override_settings(PEDIDOS_COBRO_HABILITADO=True)
class CobroSolicitudApiTests(CasoReal):
    def setUp(self):
        super().setUp()
        ctx, _, pedido = self.crear()
        pedido = self.cotizar(ctx, pedido)
        self.pedido = self.nucleo.aceptar_cotizacion(
            ctx, **self.datos_aceptacion(ctx, pedido)
        ).data["pedido"]
        self.comercio = self.driver._comercio("comercio")
        crear_cuenta(self.comercio)
        usuario = User.objects.create_user(username="tendero")
        Membresia.objects.create(usuario=usuario, comercio=self.comercio)
        self.cliente = APIClient()
        self.cliente.force_login(usuario)
        self.ruta = f"/api/pedidos/{self.pedido.id}/cobro/"

    def test_solicitar_reserva_y_replay_no_crea_otro_intento(self):
        datos = {
            "accion": "solicitar",
            "command_key": "cobro",
            "expected_version": self.pedido.version,
            "canal": "qr_venta",
        }
        primero = self.cliente.post(self.ruta, datos, format="json")
        self.assertEqual(primero.status_code, 201, primero.content)
        segundo = self.cliente.post(self.ruta, datos, format="json")
        self.assertEqual(segundo.status_code, 200, segundo.content)
        self.assertEqual(IntentoCobro.objects.count(), 1)
        self.assertEqual(IntentoCobro.objects.get().estado, "reservado")

    def test_telefono_invalido_no_crea_intento(self):
        datos = {
            "accion": "solicitar",
            "command_key": "cobro",
            "expected_version": self.pedido.version,
            "canal": "notificacion",
            "telefono_bancario_confirmado": "123",
        }
        respuesta = self.cliente.post(self.ruta, datos, format="json")
        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(IntentoCobro.objects.exists())

    def test_tendero_activa_el_mismo_intento_en_espera(self):
        cuenta = self.comercio.cuenta_por_defecto
        ocupado = IntentoCobro.objects.create(
            origen="legado",
            comercio=self.comercio,
            canal="qr_venta",
            estado="reservado",
            importe_efectivo_centavos=100,
            demo_mode=False,
            politica_cobro_version="normal-1",
            cuenta=cuenta,
            pey_bank_account_id=cuenta.pey_bank_account_id,
            concepto="ocupado",
            expiracion_s=600,
            clave_legado="ocupado",
        )
        respuesta = self.cliente.post(
            self.ruta,
            {
                "accion": "solicitar",
                "command_key": "espera",
                "expected_version": self.pedido.version,
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        espera = IntentoCobro.objects.get(origen="pedido")
        self.assertEqual(espera.estado, "en_espera")
        ocupado.estado = "descartado"
        ocupado.save(update_fields=["estado"])
        espera.pedido.refresh_from_db()
        respuesta = self.cliente.post(
            self.ruta,
            {
                "accion": "activar_espera",
                "command_key": "activar",
                "expected_version": espera.pedido.version,
                "intento_id": str(espera.pk),
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        espera.refresh_from_db()
        self.assertEqual(espera.estado, "reservado")
        self.assertEqual(espera.cuenta_id, cuenta.pk)

    def test_detalle_incluye_autoria_de_entrega_vacia(self):
        respuesta = self.cliente.get(f"/api/pedidos/{self.pedido.id}/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(
            respuesta.json()["data"]["entrega"],
            {
                "listo_en": None,
                "listo_por": None,
                "entregado_en": None,
                "entregado_por": None,
            },
        )
