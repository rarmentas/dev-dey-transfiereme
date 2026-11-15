"""Cancelación de pedidos y protección de cobros activos."""

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from ambito.models import Comercio, Membresia
from ambito.tests.soporte import crear_cuenta
from movimientos.models import Cobro, Movimiento
from pedidos.models import Aceptacion, EventoPedido, IntentoCobro, Pedido
from pedidos.tests.soporte_real import CasoReal


class CancelacionTests(CasoReal):
    def setUp(self):
        super().setUp()
        self.ctx, _, self.dto = self.crear()
        self.pedido = Pedido.objects.get(pk=self.dto.id)
        self.comercio = self.pedido.comercio
        self.usuario = get_user_model().objects.create_user(username="tendero")
        Membresia.objects.create(usuario=self.usuario, comercio=self.comercio)
        self.cliente = APIClient()
        self.cliente.force_login(self.usuario)
        self.ruta = f"/api/pedidos/{self.pedido.pk}/cancelar/"

    def cancelar(self, clave="cancelar", version=None):
        return self.cliente.post(
            self.ruta,
            {"command_key": clave, "expected_version": version or self.pedido.version},
            format="json",
        )

    def intento(self, estado):
        dto = self.cotizar(self.ctx, self.dto)
        self.nucleo.aceptar_cotizacion(
            self.ctx, **self.datos_aceptacion(self.ctx, dto)
        )
        self.pedido.refresh_from_db()
        cuenta = crear_cuenta(self.comercio)
        aceptacion = Aceptacion.objects.get(pedido=self.pedido)
        return IntentoCobro.objects.create(
            origen="pedido",
            comercio=self.comercio,
            pedido=self.pedido,
            aceptacion=aceptacion,
            cotizacion=aceptacion.cotizacion,
            canal="qr_venta",
            estado=estado,
            importe_efectivo_centavos=2500,
            demo_mode=False,
            politica_cobro_version="normal-1",
            cuenta=cuenta if estado != "en_espera" else None,
            pey_bank_account_id=cuenta.pey_bank_account_id if estado != "en_espera" else "",
            concepto="Pedido",
            expiracion_s=600,
        )

    def test_cancela_en_cada_estado_permitido(self):
        for estado in ("borrador", "en_revision", "cotizado", "aceptado"):
            with self.subTest(estado=estado):
                pedido = self.pedido if estado == "borrador" else Pedido.objects.get(
                    pk=self.crear(f"-{estado}")[2].id
                )
                Pedido.objects.filter(pk=pedido.pk).update(estado=estado)
                ruta = f"/api/pedidos/{pedido.pk}/cancelar/"
                respuesta = self.cliente.post(
                    ruta,
                    {"command_key": f"cancelar-{estado}", "expected_version": pedido.version},
                    format="json",
                )
                self.assertEqual(respuesta.status_code, 200, respuesta.content)
                pedido.refresh_from_db()
                self.assertEqual((pedido.estado, pedido.abierto), ("cerrado", False))
                self.assertEqual(pedido.version, 2)
                self.assertEqual(
                    EventoPedido.objects.filter(pedido=pedido, tipo="pedido.cancelado").count(), 1
                )

    def test_replay_no_duplica_evento_y_clave_distinta_no_reabre(self):
        primera = self.cancelar()
        repetida = self.cancelar()
        self.assertEqual(primera.status_code, 200)
        self.assertTrue(repetida.json()["replayed"])
        self.assertEqual(primera.json()["data"], repetida.json()["data"])
        self.assertEqual(
            EventoPedido.objects.filter(pedido=self.pedido, tipo="pedido.cancelado").count(), 1
        )
        self.assertEqual(self.cancelar("otra").json()["codigo"], "VERSION_OBSOLETA")

    def test_cobro_en_curso_bloquea_y_no_cambia_nada(self):
        intento = self.intento("enviando")
        for estado in ("enviando", "pendiente", "incierto"):
            with self.subTest(estado=estado):
                IntentoCobro.objects.filter(pk=intento.pk).update(estado=estado)
                respuesta = self.cancelar()
                self.assertEqual(respuesta.status_code, 409)
                self.assertEqual(respuesta.json()["codigo"], "COBRO_EN_CURSO")
                self.assertTrue(
                    self.cliente.get(f"/api/pedidos/{self.pedido.pk}/").json()["data"]["cobro_en_curso"]
                )
                self.pedido.refresh_from_db()
                self.assertTrue(self.pedido.abierto)
        self.assertFalse(EventoPedido.objects.filter(tipo="pedido.cancelado").exists())

    def _comprobar_descarte(self, estado):
        intento = self.intento(estado)
        respuesta = self.cancelar()
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        intento.refresh_from_db()
        self.assertEqual(intento.estado, "descartado")
        self.assertEqual(intento.motivo_descarte, "pedido_cancelado")

    def test_descarta_reservado(self):
        self._comprobar_descarte("reservado")

    def test_descarta_en_espera(self):
        self._comprobar_descarte("en_espera")

    def test_vence_movimiento_pendiente_al_descartar_reserva(self):
        intento = self.intento("reservado")
        cobro = Cobro.objects.create(
            comercio=self.comercio,
            cuenta=intento.cuenta,
            canal="qr_venta",
            monto="25.00",
            concepto="Pedido",
            pey_qr_id="qr-cancelacion",
            qr_string="qr-prueba",
        )
        movimiento = Movimiento.objects.create(
            comercio=self.comercio,
            cobro=cobro,
            canal="qr_venta",
            monto="25.00",
            concepto="Pedido",
            estado="pendiente",
            origen="origen_pey",
        )
        intento.cobro = cobro
        intento.save(update_fields=["cobro"])
        self.assertEqual(self.cancelar().status_code, 200)
        movimiento.refresh_from_db()
        self.assertEqual(movimiento.estado, "vencido")

    def test_solo_miembros_del_comercio(self):
        self.cliente.logout()
        self.assertEqual(self.cancelar().status_code, 403)
        ajeno = get_user_model().objects.create_user(username="ajeno")
        otro = Comercio.objects.create(nombre="Otro")
        Membresia.objects.create(usuario=ajeno, comercio=otro)
        self.cliente.force_login(ajeno)
        self.assertEqual(self.cancelar().status_code, 404)
        self.cliente.force_login(self.usuario)
        self.assertEqual(self.cancelar().status_code, 200)

    def test_dueno_puede_cancelar(self):
        Membresia.objects.filter(usuario=self.usuario).update(es_dueno=True)
        self.assertEqual(self.cancelar().status_code, 200)
