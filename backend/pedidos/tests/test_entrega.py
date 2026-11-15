"""Preparación y entrega requieren pago y conservan autoría."""

from ambito.tests.soporte import crear_cuenta
from django.contrib.auth import get_user_model

from pedidos.contratos.v1 import CodigoError
from pedidos.errores import ErrorNucleo
from pedidos.models import Aceptacion, EventoPedido, IntentoCobro, Pedido
from pedidos.servicios.entrega import operar
from pedidos.tests.soporte_real import CasoReal


class EntregaTests(CasoReal):
    def setUp(self):
        super().setUp()
        ctx, _, dto = self.crear()
        self.dto = self.cotizar(ctx, dto)
        self.dto = self.nucleo.aceptar_cotizacion(
            ctx, **self.datos_aceptacion(ctx, self.dto)
        ).data["pedido"]
        self.pedido = Pedido.objects.get(pk=self.dto.id)
        self.usuario = get_user_model().objects.create_user(username="tendero")

    def datos(self, clave, version=None):
        return {"command_key": clave, "expected_version": version or self.dto.version}

    def test_exige_pago_y_listo_en_orden(self):
        with self.assertRaises(ErrorNucleo) as exc:
            operar(self.pedido.comercio, self.pedido.id, self.datos("a"), self.usuario)
        self.assertEqual(exc.exception.codigo, CodigoError.PAGO_NO_CONFIRMADO)
        with self.assertRaises(ErrorNucleo) as exc:
            operar(
                self.pedido.comercio,
                self.pedido.id,
                self.datos("b"),
                self.usuario,
                entregado=True,
            )
        self.assertEqual(exc.exception.codigo, CodigoError.PREPARACION_INVALIDA)
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.preparacion, "pendiente")
        self.assertFalse(self.pedido.listo_en)

    def test_acciones_guardan_actor_fecha_y_evento_unico(self):
        cuenta = crear_cuenta(self.pedido.comercio)
        aceptacion = Aceptacion.objects.get(pk=self.dto.aceptacion.id)
        IntentoCobro.objects.create(
            origen="pedido",
            comercio=self.pedido.comercio,
            pedido=self.pedido,
            aceptacion=aceptacion,
            cotizacion=aceptacion.cotizacion,
            canal="qr_venta",
            estado="pagado",
            importe_efectivo_centavos=2500,
            demo_mode=False,
            politica_cobro_version="normal-1",
            cuenta=cuenta,
            pey_bank_account_id=cuenta.pey_bank_account_id,
            concepto="venta",
            expiracion_s=600,
        )
        listo = operar(
            self.pedido.comercio, self.pedido.id, self.datos("listo"), self.usuario
        )
        repetido = operar(
            self.pedido.comercio,
            self.pedido.id,
            self.datos("otra", self.dto.version),
            self.usuario,
        )
        self.assertEqual(repetido.data["pedido"].version, listo.data["pedido"].version)
        operar(
            self.pedido.comercio,
            self.pedido.id,
            self.datos("entregar", listo.data["pedido"].version),
            self.usuario,
            entregado=True,
        )
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.preparacion, "entregado")
        self.assertEqual(self.pedido.estado, "cerrado")
        self.assertFalse(self.pedido.abierto)
        self.assertEqual(self.pedido.listo_por, self.usuario)
        self.assertEqual(self.pedido.entregado_por, self.usuario)
        self.assertIsNotNone(self.pedido.listo_en)
        self.assertIsNotNone(self.pedido.entregado_en)
        from ambito.models import Membresia
        from rest_framework.test import APIClient

        Membresia.objects.create(usuario=self.usuario, comercio=self.pedido.comercio)
        cliente = APIClient()
        cliente.force_login(self.usuario)
        detalle = cliente.get(f"/api/pedidos/{self.pedido.pk}/").json()["data"][
            "entrega"
        ]
        self.assertEqual(detalle["listo_por"], self.usuario.pk)
        self.assertEqual(detalle["entregado_por"], self.usuario.pk)
        self.assertTrue(detalle["listo_en"])
        self.assertTrue(detalle["entregado_en"])
        self.assertEqual(
            EventoPedido.objects.filter(
                pedido=self.pedido, tipo="pedido.listo"
            ).count(),
            1,
        )
        self.assertEqual(
            EventoPedido.objects.filter(
                pedido=self.pedido, tipo="pedido.entregado"
            ).count(),
            1,
        )
