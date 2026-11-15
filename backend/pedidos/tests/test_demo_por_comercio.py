"""El modo y la política pertenecen a cada comercio."""

from ambito.models import Comercio
from config.modo import modo_de_comercio
from pedidos.tests.soporte_real import CasoReal


class DemoPorComercioTests(CasoReal):
    def test_cotizaciones_y_cambio_de_modo_aislados(self):
        ctx_normal, _, pedido_normal = self.crear("normal")
        normal = self.driver._comercio("comercio")
        pedido_normal = self.cotizar(ctx_normal, pedido_normal)
        self.assertEqual(
            (
                pedido_normal.cotizacion.total_comercial_centavos,
                pedido_normal.cotizacion.importe_efectivo_centavos,
                pedido_normal.cotizacion.demo_mode,
                pedido_normal.cotizacion.politica_cobro_version,
            ),
            (2500, 2500, False, "normal-1"),
        )
        demo = Comercio.objects.create(nombre="demo", es_demo=True)
        self.driver.comercios["comercio"] = demo
        ctx_demo, _, pedido_demo = self.crear("demo")
        pedido_demo = self.cotizar(ctx_demo, pedido_demo)
        self.assertEqual(
            (
                pedido_demo.cotizacion.total_comercial_centavos,
                pedido_demo.cotizacion.importe_efectivo_centavos,
                pedido_demo.cotizacion.demo_mode,
                pedido_demo.cotizacion.politica_cobro_version,
            ),
            (2500, 1, True, "demo-1"),
        )
        self.assertFalse(modo_de_comercio(normal).demo)
        datos = self.datos_aceptacion(ctx_demo, pedido_demo)
        Comercio.objects.filter(pk=demo.pk).update(es_demo=False)
        self.assertTrue(demo.es_demo)
        self.assertFalse(modo_de_comercio(demo).demo)
        resultado = self.nucleo.aceptar_cotizacion(ctx_demo, **datos)
        self.assertFalse(resultado.ok)
        self.assertEqual(resultado.error.code.value, "MODO_CAMBIO")

    def test_cotizacion_normal_no_se_acepta_tras_pasar_a_demo(self):
        ctx, _, pedido = self.crear("normal")
        comercio = self.driver._comercio("comercio")
        pedido = self.cotizar(ctx, pedido)
        datos = self.datos_aceptacion(ctx, pedido)
        self.assertFalse(comercio.es_demo)
        Comercio.objects.filter(pk=comercio.pk).update(es_demo=True)
        self.assertTrue(modo_de_comercio(comercio).demo)
        respuesta = self.nucleo.aceptar_cotizacion(ctx, **datos)
        self.assertFalse(respuesta.ok)
        self.assertEqual(respuesta.error.code.value, "MODO_CAMBIO")

    def test_demo_no_requiere_cuenta_y_normal_si(self):
        from django.test import override_settings

        from pedidos.errores import ErrorNucleo
        from pedidos.servicios.cobros import _destino

        demo = Comercio.objects.create(nombre="demo", es_demo=True)
        normal = Comercio.objects.create(nombre="normal")
        destino = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
        with override_settings(DEMO_PEY_BANK_ACCOUNT_ID=destino):
            self.assertEqual(_destino(demo, True, 1), (None, destino))
            with self.assertRaises(ErrorNucleo) as error:
                _destino(normal, False, 2500)
        self.assertEqual(error.exception.codigo.value, "CUENTA_NO_ACTIVE")


class CobrosPorComercioTests(CasoReal):
    def preparar(self, nombre, demo):
        from ambito.tests.soporte import crear_cuenta
        from pedidos.models import Aceptacion, IntentoCobro

        comercio = Comercio.objects.create(nombre=nombre, es_demo=demo)
        cuenta = None if demo else crear_cuenta(comercio)
        self.driver.comercios["comercio"] = comercio
        ctx, _, pedido = self.crear(nombre)
        pedido = self.cotizar(ctx, pedido)
        politica = "demo-1" if demo else "normal-1"
        self.assertEqual(pedido.cotizacion.politica_cobro_version, politica)
        respuesta = self.nucleo.aceptar_cotizacion(
            ctx, **self.datos_aceptacion(ctx, pedido)
        )
        self.assertTrue(respuesta.ok, respuesta.error)
        pedido = respuesta.data["pedido"]
        aceptacion = Aceptacion.objects.get(pk=pedido.aceptacion.id)
        self.assertEqual(aceptacion.politica_cobro_version, politica)
        respuesta = self.nucleo.solicitar_cobro(
            ctx,
            contrato_version="1.0",
            command_key="cobrar-" + nombre,
            pedido_id=pedido.id,
            expected_version=pedido.version,
            aceptacion_id=pedido.aceptacion.id,
            canal="qr_venta",
        )
        self.assertTrue(respuesta.ok, respuesta.error)
        intento = IntentoCobro.objects.get(aceptacion=aceptacion)
        self.assertEqual(intento.politica_cobro_version, politica)
        return comercio, cuenta, intento

    def test_worker_envia_ambos_modos_y_demo_sin_cuenta(self):
        from decimal import Decimal
        from django.test import override_settings
        from movimientos.models import Movimiento
        from pedidos.models import EventoPedido
        from pedidos.servicios.despacho import ciclo
        from pedidos.tests.soporte_cobro import PuertoPeyFalso

        destino = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
        with override_settings(
            PEDIDOS_COBRO_HABILITADO=True, DEMO_PEY_BANK_ACCOUNT_ID=destino
        ):
            demo, _, intento_demo = self.preparar("demo", True)
            normal, cuenta, intento_normal = self.preparar("normal", False)
            self.assertFalse(demo.cuentas.exists())
            self.assertIsNone(intento_demo.cuenta_id)
            puerto = PuertoPeyFalso()
            original = puerto.crear_qr

            def crear_qr(**datos):
                puerto.siguiente_id = "qr-" + str(len(puerto.llamadas))
                return original(**datos)

            puerto.crear_qr = crear_qr
            ciclo(puerto)
        self.assertEqual(len(puerto.llamadas), 2)
        self.assertCountEqual(
            [(d["monto"], d["bank_account_id"]) for _, d in puerto.llamadas],
            [
                (Decimal("0.01"), destino),
                (Decimal("25.00"), cuenta.pey_bank_account_id),
            ],
        )
        for intento, monto, banco, cuenta_id in (
            (intento_demo, Decimal("0.01"), destino, None),
            (intento_normal, Decimal("25.00"), cuenta.pey_bank_account_id, cuenta.pk),
        ):
            intento.refresh_from_db()
            self.assertEqual(intento.estado, "pendiente")
            self.assertEqual(
                (
                    intento.cobro.monto,
                    intento.cobro.pey_bank_account_id,
                    intento.cobro.cuenta_id,
                ),
                (monto, banco, cuenta_id),
            )
            movimiento = Movimiento.objects.get(cobro=intento.cobro)
            self.assertEqual(
                (movimiento.monto, movimiento.estado), (monto, "pendiente")
            )
            evento = EventoPedido.objects.get(
                pedido=intento.pedido, tipo="cobro.pendiente"
            )
            self.assertEqual(evento.intento_id, intento.pk)
            self.assertEqual(evento.snapshot["total_comercial_centavos"], 2500)
            self.assertEqual(
                evento.snapshot["importe_efectivo_centavos"], int(monto * 100)
            )
            self.assertEqual(evento.snapshot["demo_mode"], cuenta_id is None)
            self.assertEqual(evento.snapshot["pago_estado"], "pendiente")
        self.assertNotEqual(demo.pk, normal.pk)

    def test_cambio_politica_normal_descarta_solo_normal(self):
        from decimal import Decimal
        from unittest.mock import patch
        from django.test import override_settings
        from config import modo
        from pedidos.servicios.despacho import enviar_intento
        from pedidos.tests.soporte_cobro import PuertoPeyFalso

        with override_settings(
            PEDIDOS_COBRO_HABILITADO=True,
            DEMO_PEY_BANK_ACCOUNT_ID="01ARZ3NDEKTSV4RRFFQ69G5FAV",
        ):
            _, _, demo = self.preparar("demo", True)
            _, _, normal = self.preparar("normal", False)
            puerto = PuertoPeyFalso()
            with patch.object(modo, "POLITICA_NORMAL", "normal-2"):
                resultado = enviar_intento(normal.pk, puerto)
                self.assertEqual(
                    (resultado.estado, resultado.motivo_descarte),
                    ("descartado", "condiciones_cambiaron"),
                )
                self.assertEqual(puerto.llamadas, [])
                self.assertEqual(enviar_intento(demo.pk, puerto).estado, "pendiente")
            self.assertEqual(len(puerto.llamadas), 1)
            self.assertEqual(puerto.llamadas[0][1]["monto"], Decimal("0.01"))

    def test_reserva_demo_en_espera_fija_destino_sin_cuenta(self):
        from django.test import override_settings
        from pedidos.models import IntentoCobro
        from pedidos.servicios.cobros import activar_espera

        destino = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
        with override_settings(
            PEDIDOS_COBRO_HABILITADO=True, DEMO_PEY_BANK_ACCOUNT_ID=destino
        ):
            comercio, _, intento = self.preparar("demo", True)
            IntentoCobro.objects.filter(pk=intento.pk).update(
                estado="en_espera", cuenta=None, pey_bank_account_id=""
            )
            respuesta = activar_espera(
                comercio,
                intento.pedido_id,
                intento.pk,
                {"command_key": "activar", "expected_version": intento.pedido.version},
            )
            self.assertTrue(respuesta.ok, respuesta.error)
            intento.refresh_from_db()
            self.assertEqual(
                (intento.estado, intento.cuenta_id, intento.pey_bank_account_id),
                ("reservado", None, destino),
            )

    def test_reserva_demo_descartada_si_cambia_modo_o_destino(self):
        from django.test import override_settings
        from pedidos.servicios.despacho import enviar_intento
        from pedidos.tests.soporte_cobro import PuertoPeyFalso

        destino = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
        with override_settings(
            PEDIDOS_COBRO_HABILITADO=True, DEMO_PEY_BANK_ACCOUNT_ID=destino
        ):
            comercio, _, intento = self.preparar("demo", True)
            puerto = PuertoPeyFalso()
            with override_settings(
                DEMO_PEY_BANK_ACCOUNT_ID="01ARZ3NDEKTSV4RRFFQ69G5FAW"
            ):
                resultado = enviar_intento(intento.pk, puerto)
            self.assertEqual(
                (resultado.estado, resultado.motivo_descarte),
                ("descartado", "destino_demo_invalido"),
            )
            self.assertEqual(puerto.llamadas, [])
            self.driver.comercios["comercio"] = comercio
            ctx, _, pedido = self.crear("segundo")
            pedido = self.cotizar(ctx, pedido)
            datos = self.datos_aceptacion(ctx, pedido)
            datos["command_key"] = "aceptar-segundo"
            respuesta = self.nucleo.aceptar_cotizacion(ctx, **datos)
            self.assertTrue(respuesta.ok, respuesta.error)
            pedido = respuesta.data["pedido"]
            respuesta = self.nucleo.solicitar_cobro(
                ctx,
                contrato_version="1.0",
                command_key="segundo",
                pedido_id=pedido.id,
                expected_version=pedido.version,
                aceptacion_id=pedido.aceptacion.id,
                canal="qr_venta",
            )
            self.assertTrue(respuesta.ok, respuesta.error)
            from pedidos.models import IntentoCobro

            segundo = IntentoCobro.objects.get(aceptacion_id=pedido.aceptacion.id)
            Comercio.objects.filter(pk=comercio.pk).update(es_demo=False)
            resultado = enviar_intento(segundo.pk, puerto)
            self.assertEqual(
                (resultado.estado, resultado.motivo_descarte),
                ("descartado", "condiciones_cambiaron"),
            )
            self.assertEqual(puerto.llamadas, [])

    def test_destino_invalido_no_bloquea_cobro_normal(self):
        from decimal import Decimal
        from unittest.mock import patch

        from django.test import override_settings
        from pedidos.models import IntentoCobro
        from pedidos.servicios.despacho import enviar_intento
        from pedidos.tests.soporte_cobro import PuertoPeyFalso

        demo = Comercio.objects.create(nombre="demo", es_demo=True)
        self.driver.comercios["comercio"] = demo
        ctx, _, pedido = self.crear("demo")
        pedido = self.cotizar(ctx, pedido)
        pedido = self.nucleo.aceptar_cotizacion(
            ctx, **self.datos_aceptacion(ctx, pedido)
        ).data["pedido"]
        puerto = PuertoPeyFalso()
        with override_settings(PEDIDOS_COBRO_HABILITADO=True):
            for destino in ("", "invalido"):
                with (
                    self.subTest(destino=destino),
                    override_settings(DEMO_PEY_BANK_ACCOUNT_ID=destino),
                    patch("pedidos.servicios.despacho.obtener_puerto") as obtener,
                ):
                    respuesta = self.nucleo.solicitar_cobro(
                        ctx,
                        contrato_version="1.0",
                        command_key="demo",
                        pedido_id=pedido.id,
                        expected_version=pedido.version,
                        aceptacion_id=pedido.aceptacion.id,
                        canal="qr_venta",
                    )
                    self.assertFalse(respuesta.ok)
                    self.assertEqual(
                        respuesta.error.code.value, "DEMO_DESTINO_NO_PERMITIDO"
                    )
                    self.assertFalse(IntentoCobro.objects.exists())
                    obtener.assert_not_called()
                    self.assertEqual(puerto.llamadas, [])
            with override_settings(DEMO_PEY_BANK_ACCOUNT_ID=""):
                _, cuenta, intento = self.preparar("normal", False)
                self.assertEqual(enviar_intento(intento.pk, puerto).estado, "pendiente")
                self.assertEqual(puerto.llamadas[0][1]["monto"], Decimal("25.00"))
                self.assertEqual(
                    puerto.llamadas[0][1]["bank_account_id"], cuenta.pey_bank_account_id
                )

    def test_flip_demo_no_afecta_reserva_normal(self):
        from django.test import override_settings
        from pedidos.servicios.despacho import enviar_intento
        from pedidos.tests.soporte_cobro import PuertoPeyFalso

        with override_settings(
            PEDIDOS_COBRO_HABILITADO=True,
            DEMO_PEY_BANK_ACCOUNT_ID="01ARZ3NDEKTSV4RRFFQ69G5FAV",
        ):
            demo, _, _ = self.preparar("demo", True)
            _, cuenta, intento = self.preparar("normal", False)
            Comercio.objects.filter(pk=demo.pk).update(es_demo=False)
            puerto = PuertoPeyFalso()
            self.assertEqual(enviar_intento(intento.pk, puerto).estado, "pendiente")
            self.assertEqual(len(puerto.llamadas), 1)
            self.assertEqual(
                puerto.llamadas[0][1]["bank_account_id"], cuenta.pey_bank_account_id
            )
