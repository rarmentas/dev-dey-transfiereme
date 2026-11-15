"""El destino demo nunca coincide con la cuenta de un comercio."""

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import wait as esperar
from contextlib import nullcontext
from io import StringIO
from threading import Event
from unittest.mock import patch

from ambito.cuenta import id_reservado_demo
from ambito.models import Comercio, CuentaCobro
from ambito.tests.soporte import crear_cuenta
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import close_old_connections, connections
from django.test import override_settings
from pey.cuentas import CuentaPey

from pedidos.models import IntentoCobro
from pedidos.servicios.despacho import ciclo, enviar_intento
from pedidos.tests.soporte_cobro import PuertoPeyFalso
from pedidos.tests.soporte_real import CasoReal

DESTINO = "01ARZ3NDEKTSV4RRFFQ69G5FAV"


@override_settings(PEDIDOS_COBRO_HABILITADO=True)
class DestinoDemoReservadoTests(CasoReal):
    def designar_y_aceptar(self):
        demo = Comercio.objects.create(nombre="demo")
        call_command(
            "designar_comercio_demo",
            "--comercio",
            str(demo.pk),
            "--si",
            stdout=StringIO(),
            stderr=StringIO(),
        )
        self.driver.comercios["comercio"] = demo
        ctx, _, pedido = self.crear("demo")
        pedido = self.cotizar(ctx, pedido)
        respuesta = self.nucleo.aceptar_cotizacion(
            ctx, **self.datos_aceptacion(ctx, pedido)
        )
        self.assertTrue(respuesta.ok, respuesta.error)
        return ctx, respuesta.data["pedido"]

    def solicitar(self, ctx, pedido):
        return self.nucleo.solicitar_cobro(
            ctx,
            contrato_version="1.0",
            command_key="cobrar-demo",
            pedido_id=pedido.id,
            expected_version=pedido.version,
            aceptacion_id=pedido.aceptacion.id,
            canal="qr_venta",
        )

    def cuenta_incierta(self):
        cuenta = crear_cuenta(
            Comercio.objects.create(nombre="B"), "pending", predeterminada=False
        )
        CuentaCobro.objects.filter(pk=cuenta.pk).update(
            pey_bank_account_id="", registro_estado="incierto"
        )
        cuenta.refresh_from_db()
        return cuenta

    def enlazar(self, cuenta):
        with patch(
            "ambito.management.commands.enlazar_cuenta_pey.consultar_cuenta",
            return_value=CuentaPey(DESTINO, "ACTIVE", cuenta.clabe),
        ):
            call_command(
                "enlazar_cuenta_pey",
                cuenta=str(cuenta.pk),
                pey_id=DESTINO,
                stdout=StringIO(),
            )

    def test_destino_configurado_despues_es_cuenta_de_otro_comercio(self):
        ajena = crear_cuenta(Comercio.objects.create(nombre="B"))
        with override_settings(DEMO_PEY_BANK_ACCOUNT_ID=""):
            ctx, pedido = self.designar_y_aceptar()
        puerto = PuertoPeyFalso()
        with (
            override_settings(DEMO_PEY_BANK_ACCOUNT_ID=ajena.pey_bank_account_id),
            patch("pedidos.servicios.despacho.obtener_puerto") as obtener,
        ):
            respuesta = self.solicitar(ctx, pedido)
            ciclo(puerto)
        self.assertFalse(respuesta.ok)
        self.assertEqual(respuesta.error.code.value, "DEMO_DESTINO_NO_PERMITIDO")
        self.assertFalse(IntentoCobro.objects.exists())
        obtener.assert_not_called()
        self.assertEqual(puerto.llamadas, [])

    def test_enlace_posterior_del_destino_demo_se_rechaza(self):
        with override_settings(DEMO_PEY_BANK_ACCOUNT_ID=DESTINO):
            ctx, pedido = self.designar_y_aceptar()
            self.assertTrue(self.solicitar(ctx, pedido).ok)
            intento = IntentoCobro.objects.get(demo_mode=True, estado="reservado")
            for oculto in (False, True):
                cuenta = self.cuenta_incierta()
                with (
                    self.subTest(oculto=oculto),
                    patch("ambito.cuenta.destino_demo", return_value=None)
                    if oculto
                    else nullcontext(),
                ):
                    with self.assertRaises(CommandError):
                        self.enlazar(cuenta)
                    cuenta.refresh_from_db()
                    self.assertEqual(
                        (cuenta.registro_estado, cuenta.pey_bank_account_id),
                        ("incierto", ""),
                    )
            puerto = PuertoPeyFalso()
            enviado = enviar_intento(intento.pk, puerto)
        self.assertEqual(enviado.estado, "pendiente")
        self.assertEqual(
            [datos["bank_account_id"] for _, datos in puerto.llamadas], [DESTINO]
        )
        self.assertFalse(
            CuentaCobro.objects.filter(pey_bank_account_id=DESTINO).exists()
        )

    def test_cuenta_con_el_destino_tras_reservar_se_descarta_sin_red(self):
        with override_settings(DEMO_PEY_BANK_ACCOUNT_ID=DESTINO):
            ctx, pedido = self.designar_y_aceptar()
            self.assertTrue(self.solicitar(ctx, pedido).ok)
            intento = IntentoCobro.objects.get(demo_mode=True, estado="reservado")
            cuenta = crear_cuenta(Comercio.objects.create(nombre="B"))
            CuentaCobro.objects.filter(pk=cuenta.pk).update(pey_bank_account_id=DESTINO)
            puerto = PuertoPeyFalso()
            intento = enviar_intento(intento.pk, puerto)
        self.assertEqual(
            (intento.estado, intento.motivo_descarte),
            ("descartado", "destino_demo_invalido"),
        )
        self.assertEqual(puerto.llamadas, [])

    def test_carrera_enlace_durante_el_envio_demo_se_rechaza(self):
        with override_settings(DEMO_PEY_BANK_ACCOUNT_ID=DESTINO):
            ctx, pedido = self.designar_y_aceptar()
            self.assertTrue(self.solicitar(ctx, pedido).ok)
            intento = IntentoCobro.objects.get(demo_mode=True, estado="reservado")
            cuenta = self.cuenta_incierta()
            en_red, liberar = Event(), Event()
            puerto = PuertoPeyFalso()
            original = puerto.crear_qr

            def crear_qr(**datos):
                en_red.set()
                liberar.wait(10)
                return original(**datos)

            puerto.crear_qr = crear_qr

            def enviar():
                close_old_connections()
                try:
                    return enviar_intento(intento.pk, puerto)
                finally:
                    connections.close_all()

            with ThreadPoolExecutor(max_workers=1) as pool:
                envio = pool.submit(enviar)
                try:
                    self.assertTrue(en_red.wait(10))
                    with patch("ambito.cuenta.destino_demo", return_value=None):
                        with self.assertRaises(CommandError):
                            self.enlazar(cuenta)
                finally:
                    liberar.set()
                enviado = envio.result(10)
        self.assertEqual(enviado.estado, "pendiente")
        self.assertEqual(len(puerto.llamadas), 1)
        cuenta.refresh_from_db()
        self.assertEqual(
            (cuenta.registro_estado, cuenta.pey_bank_account_id), ("incierto", "")
        )

    def test_carrera_enlace_bajo_candado_serializa_la_solicitud(self):
        with override_settings(DEMO_PEY_BANK_ACCOUNT_ID=DESTINO):
            ctx, pedido = self.designar_y_aceptar()
            cuenta = self.cuenta_incierta()
            dentro, seguir = Event(), Event()
            consultas = []

            def reservado(ident):
                resultado = id_reservado_demo(ident)
                consultas.append(resultado)
                if len(consultas) == 2:
                    dentro.set()
                    seguir.wait(10)
                return resultado

            def en_hilo(funcion):
                close_old_connections()
                try:
                    return funcion()
                finally:
                    connections.close_all()

            with (
                patch("ambito.cuenta.destino_demo", return_value=None),
                patch(
                    "ambito.management.commands.enlazar_cuenta_pey.id_reservado_demo",
                    side_effect=reservado,
                ),
                ThreadPoolExecutor(max_workers=2) as pool,
            ):
                enlace = pool.submit(en_hilo, lambda: self.enlazar(cuenta))
                try:
                    self.assertTrue(dentro.wait(10))
                    solicitud = pool.submit(
                        en_hilo, lambda: self.solicitar(ctx, pedido)
                    )
                    esperar([solicitud], timeout=1)
                    bloqueada = not solicitud.done()
                finally:
                    seguir.set()
                enlace.result(10)
                respuesta = solicitud.result(10)
        self.assertTrue(bloqueada)
        self.assertFalse(respuesta.ok)
        self.assertEqual(respuesta.error.code.value, "DEMO_DESTINO_NO_PERMITIDO")
        self.assertFalse(IntentoCobro.objects.exists())
