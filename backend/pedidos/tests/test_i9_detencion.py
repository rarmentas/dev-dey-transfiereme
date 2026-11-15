"""El worker drena la operación actual al recibir SIGTERM."""

import os
import signal
from unittest.mock import patch

from ambito.models import Comercio
from ambito.tests.soporte import crear_cuenta
from django.core.management import call_command
from django.test import override_settings

from pedidos.models import IntentoCobro
from pedidos.tests.soporte_cobro import PuertoPeyFalso
from pedidos.tests.soporte_real import CasoReal


@override_settings(PEDIDOS_COBRO_HABILITADO=True)
class DetencionWorkerTests(CasoReal):
    def reservar(self, sufijo):
        ctx, _, pedido = self.crear(sufijo)
        pedido = self.cotizar(ctx, pedido)
        aceptacion = self.nucleo.aceptar_cotizacion(
            ctx, **self.datos_aceptacion(ctx, pedido)
        ).data["pedido"]
        resultado = self.nucleo.solicitar_cobro(
            ctx,
            contrato_version="1.0",
            command_key="cobro" + sufijo,
            pedido_id=pedido.id,
            expected_version=aceptacion.version,
            aceptacion_id=aceptacion.aceptacion.id,
            canal="qr_venta",
        )
        self.assertTrue(resultado.ok, resultado.error)
        return IntentoCobro.objects.get(pedido_id=pedido.id)

    def test_i9_sigterm_drena_primero_sin_iniciar_el_segundo(self):
        crear_cuenta(self.driver._comercio("comercio"))
        primero = self.reservar("-uno")
        comercio2 = Comercio.objects.create(nombre="Segundo")
        crear_cuenta(comercio2)
        self.driver.comercios["comercio"] = comercio2
        segundo = self.reservar("-dos")
        puerto = PuertoPeyFalso()
        original = puerto.crear_qr

        def enviar(**kwargs):
            puerto.siguiente_id = f"qr-{len(puerto.llamadas)}"
            respuesta = original(**kwargs)
            if len(puerto.llamadas) == 1:
                os.kill(os.getpid(), signal.SIGTERM)
            return respuesta

        puerto.crear_qr = enviar
        with (
            patch(
                "pedidos.management.commands.procesar_cobros.modo_adaptador",
                return_value="desarrollo",
            ),
            patch("pedidos.servicios.despacho.obtener_puerto", return_value=puerto),
            patch("ambito.operaciones_cuenta.recuperar_abandonadas"),
            patch("ambito.operaciones_cuenta.ejecutar_pendientes"),
        ):
            call_command("procesar_cobros", intervalo=0, max_ciclos=2)
        primero.refresh_from_db()
        segundo.refresh_from_db()
        self.assertEqual(len(puerto.llamadas), 1)
        self.assertEqual(primero.estado, "pendiente")
        self.assertEqual(segundo.estado, "reservado")

    def test_i9_operaciones_de_cuenta_revisan_detencion_antes_de_cada_reclamo(self):
        from ambito.operaciones_cuenta import ejecutar_pendientes

        operaciones = [type("Op", (), {"cuenta": object()})() for _ in range(2)]
        detenido = False

        def sincronizar(*_args, **_kwargs):
            nonlocal detenido
            detenido = True

        with (
            patch("ambito.operaciones_cuenta.recuperar_abandonadas"),
            patch(
                "ambito.operaciones_cuenta.OperacionCuenta.objects.filter",
                return_value=operaciones,
            ),
            patch(
                "ambito.operaciones_cuenta.sincronizar", side_effect=sincronizar
            ) as sync,
        ):
            ejecutar_pendientes(detener=lambda: detenido)
        self.assertEqual(sync.call_count, 1)
