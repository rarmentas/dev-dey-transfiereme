"""Envío durable y recuperación de incertidumbre."""

import json
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import wait as esperar
from decimal import Decimal
from threading import Barrier, Event, Lock
from unittest.mock import patch

from ambito.candados import bloquear_cuenta
from ambito.operaciones_cuenta import sincronizar
from ambito.tests.soporte import clabe_valida, crear_cuenta
from django.db import close_old_connections, connections
from django.test import override_settings
from movimientos.models import Cobro, Movimiento
from pey.tipos import ErrorPey

from pedidos.models import IntentoCobro
from pedidos.servicios.despacho import enviar_intento
from pedidos.tests.soporte_cobro import PuertoPeyFalso
from pedidos.tests.soporte_real import CasoReal


@override_settings(PEDIDOS_COBRO_HABILITADO=True)
class DespachoTests(CasoReal):
    def setUp(self):
        super().setUp()
        self.ctx, _, pedido = self.crear()
        pedido = self.cotizar(self.ctx, pedido)
        self.pedido = self.nucleo.aceptar_cotizacion(
            self.ctx, **self.datos_aceptacion(self.ctx, pedido)
        ).data["pedido"]
        self.comercio = self.driver._comercio("comercio")
        crear_cuenta(self.comercio)

    def solicitar(self, clave="cobrar", **cambios):
        datos = dict(
            contrato_version="1.0",
            command_key=clave,
            pedido_id=self.pedido.id,
            expected_version=self.pedido.version,
            aceptacion_id=self.pedido.aceptacion.id,
            canal="qr_venta",
        )
        datos.update(cambios)
        return self.nucleo.solicitar_cobro(self.ctx, **datos)

    def test_intento_existe_antes_de_red_y_misma_aceptacion_no_reenvia(self):
        respuesta = self.solicitar()
        self.assertTrue(respuesta.ok, respuesta.error)
        intento = IntentoCobro.objects.get()
        puerto = PuertoPeyFalso()
        enviado = enviar_intento(intento.pk, puerto)
        self.assertEqual(enviado.estado, "pendiente")
        self.assertIsNotNone(enviado.cobro_id)
        self.assertEqual(len(puerto.llamadas), 1)
        replay = self.solicitar("otra")
        self.assertTrue(replay.ok, replay.error)
        enviar_intento(intento.pk, puerto)
        self.assertEqual(len(puerto.llamadas), 1)

    def test_timeout_deja_incierto_y_no_reenvia(self):
        self.assertTrue(self.solicitar().ok)
        intento = IntentoCobro.objects.get()
        puerto = PuertoPeyFalso()
        puerto.fallar_con = ErrorPey(
            "NO_DISPONIBLE", "timeout", puede_haberse_creado=True
        )
        self.assertEqual(enviar_intento(intento.pk, puerto).estado, "incierto")
        enviar_intento(intento.pk, puerto)
        self.assertEqual(len(puerto.llamadas), 1)

    def test_request_id_base64_se_persiste_y_recorta(self):
        from ambito.models import Comercio

        casos = (
            ("req_+/=", "req_+/="),
            ("a" * 63 + "=" + "b" * 12, "a" * 63 + "="),
            ("req.con-guion", "req.con-guion"),
            (None, ""),
            (123, ""),
            ("req\ninyectado", ""),
        )
        for n, (recibido, esperado) in enumerate(casos):
            with self.subTest(request_id=recibido):
                comercio = Comercio.objects.create(nombre=f"requestId-{n}")
                cuenta = crear_cuenta(comercio)
                intento = IntentoCobro.objects.create(
                    origen="legado",
                    estado="reservado",
                    comercio=comercio,
                    cuenta=cuenta,
                    pey_bank_account_id=cuenta.pey_bank_account_id,
                    canal="qr_venta",
                    importe_efectivo_centavos=2500,
                    demo_mode=False,
                    politica_cobro_version="normal-1",
                    concepto="requestId",
                    expiracion_s=600,
                    clave_legado=f"req-{n}",
                )
                puerto = PuertoPeyFalso()
                puerto.fallar_con = ErrorPey(
                    "RESPUESTA_INVALIDA",
                    "estado inesperado",
                    recibido,
                    puede_haberse_creado=True,
                )
                resultado = enviar_intento(intento.pk, puerto)
                self.assertEqual(resultado.estado, "incierto")
                self.assertEqual(resultado.request_id, esperado)
                self.assertEqual(len(puerto.llamadas), 1)

    def test_reservado_a_enviando_tiene_un_ganador(self):
        self.assertTrue(self.solicitar().ok)
        intento = IntentoCobro.objects.get()
        puerto = PuertoPeyFalso()
        barrera = Barrier(2)
        mutex = Lock()
        original = puerto.crear_qr

        def crear(**datos):
            with mutex:
                return original(**datos)

        puerto.crear_qr = crear

        def ejecutar():
            close_old_connections()
            try:
                barrera.wait()
                enviar_intento(intento.pk, puerto)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda _: ejecutar(), range(2)))
        self.assertEqual(len(puerto.llamadas), 1)
        intento.refresh_from_db()
        self.assertEqual(intento.estado, "pendiente")

    def test_otra_intencion_no_modifica_el_intento(self):
        self.assertTrue(self.solicitar().ok)
        intento = IntentoCobro.objects.get()
        resultado = self.solicitar(
            "otra", canal="notificacion", telefono_bancario_confirmado="1234567890"
        )
        self.assertFalse(resultado.ok)
        self.assertEqual(resultado.error.code.value, "INTENCION_DISTINTA")
        intento.refresh_from_db()
        self.assertEqual(intento.canal, "qr_venta")
        self.assertEqual(intento.estado, "reservado")

    def test_espera_solo_se_activa_por_accion_tendero_con_default_vigente(self):
        from pedidos.servicios.cobros import activar_espera

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
            concepto="venta",
            expiracion_s=600,
            clave_legado="ocupado",
        )
        respuesta = self.solicitar()
        self.assertTrue(respuesta.ok, respuesta.error)
        espera = IntentoCobro.objects.get(origen="pedido")
        self.assertEqual(espera.estado, "en_espera")
        self.assertIsNone(espera.cuenta_id)
        ocupado.estado = "descartado"
        ocupado.save(update_fields=["estado"])
        segunda = crear_cuenta(self.comercio)
        otra = self.solicitar("repetir")
        self.assertTrue(otra.ok, otra.error)
        espera.refresh_from_db()
        self.assertEqual(espera.estado, "en_espera")
        respuesta = activar_espera(
            self.comercio,
            espera.pedido_id,
            espera.pk,
            {"command_key": "activar", "expected_version": otra.data["pedido"].version},
        )
        self.assertTrue(respuesta.ok)
        espera.refresh_from_db()
        self.assertEqual(espera.estado, "reservado")
        self.assertEqual(espera.cuenta_id, segunda.pk)

    def test_cambio_modo_descarta_intento_en_espera(self):
        from pedidos.servicios.cobros import activar_espera

        cuenta = self.comercio.cuenta_por_defecto
        IntentoCobro.objects.create(
            origen="legado",
            comercio=self.comercio,
            canal="qr_venta",
            estado="reservado",
            importe_efectivo_centavos=100,
            demo_mode=False,
            politica_cobro_version="normal-1",
            cuenta=cuenta,
            pey_bank_account_id=cuenta.pey_bank_account_id,
            concepto="venta",
            expiracion_s=600,
            clave_legado="ocupado",
        )
        resultado = self.solicitar()
        self.assertTrue(resultado.ok)
        espera = IntentoCobro.objects.get(origen="pedido")
        self.assertEqual(espera.estado, "en_espera")
        type(self.comercio).objects.filter(pk=self.comercio.pk).update(es_demo=True)
        activar_espera(
            self.comercio,
            espera.pedido_id,
            espera.pk,
            {
                "command_key": "activar",
                "expected_version": resultado.data["pedido"].version,
            },
        )
        espera.refresh_from_db()
        self.assertEqual(espera.estado, "descartado")
        self.assertEqual(espera.motivo_descarte, "condiciones_cambiaron")

    def test_cambio_modo_descarta_sin_llamada(self):
        self.assertTrue(self.solicitar().ok)
        intento = IntentoCobro.objects.get()
        puerto = PuertoPeyFalso()
        type(self.comercio).objects.filter(pk=self.comercio.pk).update(es_demo=True)
        enviar_intento(intento.pk, puerto)
        intento.refresh_from_db()
        self.assertEqual(intento.estado, "descartado")
        self.assertEqual(puerto.llamadas, [])

    def test_cambio_modo_no_altera_intento_ya_enviado(self):
        self.assertTrue(self.solicitar().ok)
        intento = IntentoCobro.objects.get()
        puerto = PuertoPeyFalso()
        enviar_intento(intento.pk, puerto)
        intento.refresh_from_db()
        anterior = (
            intento.estado,
            intento.importe_efectivo_centavos,
            intento.pey_bank_account_id,
            intento.demo_mode,
        )
        self.assertEqual(anterior[0], "pendiente")
        type(self.comercio).objects.filter(pk=self.comercio.pk).update(es_demo=True)
        enviar_intento(intento.pk, puerto)
        intento.refresh_from_db()
        self.assertEqual(
            (
                intento.estado,
                intento.importe_efectivo_centavos,
                intento.pey_bank_account_id,
                intento.demo_mode,
            ),
            anterior,
        )
        self.assertEqual(len(puerto.llamadas), 1)

    @override_settings(PEDIDOS_COBRO_HABILITADO=False)
    def test_compuerta_cerrada_no_crea_intento(self):
        resultado = self.solicitar()
        self.assertFalse(resultado.ok)
        self.assertEqual(resultado.error.code.value, "PROVEEDOR_NO_DISPONIBLE")
        self.assertFalse(IntentoCobro.objects.exists())

    def test_sin_default_activo_no_crea_intento(self):
        from unittest.mock import patch

        self.comercio.cuenta_por_defecto = None
        self.comercio.save(update_fields=["cuenta_por_defecto"])
        with patch("pedidos.servicios.despacho.obtener_puerto") as obtener:
            resultado = self.solicitar()
            obtener.assert_not_called()
        self.assertFalse(resultado.ok)
        self.assertEqual(resultado.error.code.value, "CUENTA_NO_ACTIVE")
        self.assertFalse(IntentoCobro.objects.exists())

    def test_demo_solo_un_centavo_a_la_cuenta_seleccionada(self):
        from ambito.models import Comercio

        self.comercio = Comercio.objects.create(nombre="Demo", es_demo=True)
        crear_cuenta(self.comercio)
        cuenta = crear_cuenta(self.comercio)
        self.driver.comercios["comercio"] = self.comercio
        ctx, _, pedido = self.crear("demo")
        pedido = self.cotizar(ctx, pedido)
        pedido = self.nucleo.aceptar_cotizacion(
            ctx, **self.datos_aceptacion(ctx, pedido)
        ).data["pedido"]
        datos = dict(
            contrato_version="1.0",
            command_key="demo",
            pedido_id=pedido.id,
            expected_version=pedido.version,
            aceptacion_id=pedido.aceptacion.id,
            canal="qr_venta",
        )
        puerto = PuertoPeyFalso()
        with override_settings(DEMO_PEY_BANK_ACCOUNT_ID=""):
            resultado = self.nucleo.solicitar_cobro(ctx, **datos)
            self.assertTrue(resultado.ok, resultado.error)
            intento = IntentoCobro.objects.get()
            self.assertEqual(intento.cuenta_id, cuenta.pk)
            self.assertEqual(intento.pey_bank_account_id, cuenta.pey_bank_account_id)
            enviar_intento(intento.pk, puerto)
        self.assertEqual(puerto.llamadas[0][1]["monto"], Decimal("0.01"))
        self.assertEqual(
            puerto.llamadas[0][1]["bank_account_id"], cuenta.pey_bank_account_id
        )

    def test_destino_normal_alterado_se_descarta_sin_red(self):
        self.assertTrue(self.solicitar().ok)
        intento = IntentoCobro.objects.get()
        IntentoCobro.objects.filter(pk=intento.pk).update(
            pey_bank_account_id="01ARZ3NDEKTSV4RRFFQ69G5FAV"
        )
        puerto = PuertoPeyFalso()
        intento = enviar_intento(intento.pk, puerto)
        self.assertEqual(intento.estado, "descartado")
        self.assertEqual(intento.motivo_descarte, "destino_invalido")
        self.assertEqual(puerto.llamadas, [])

    def test_worker_no_envia_legado_y_descarta_reserva_abandonada(self):
        from datetime import timedelta
        from unittest.mock import patch

        from django.utils import timezone

        from canales.models import LatidoCanal
        from pedidos.servicios.despacho import ciclo

        cuenta = self.comercio.cuenta_por_defecto
        intento = IntentoCobro.objects.create(
            origen="legado",
            comercio=self.comercio,
            canal="qr_venta",
            estado="reservado",
            importe_efectivo_centavos=100,
            demo_mode=False,
            politica_cobro_version="normal-1",
            cuenta=cuenta,
            pey_bank_account_id=cuenta.pey_bank_account_id,
            concepto="venta",
            expiracion_s=600,
            clave_legado="legado",
        )
        puerto = PuertoPeyFalso()
        with (
            patch("ambito.operaciones_cuenta.recuperar_abandonadas"),
            patch("ambito.operaciones_cuenta.ejecutar_pendientes"),
        ):
            ciclo(puerto)
            intento.refresh_from_db()
            self.assertEqual(intento.estado, "reservado")
            IntentoCobro.objects.filter(pk=intento.pk).update(
                creado_en=timezone.now() - timedelta(seconds=61)
            )
            ciclo(puerto)
        intento.refresh_from_db()
        self.assertEqual(intento.estado, "descartado")
        self.assertEqual(puerto.llamadas, [])
        self.assertEqual(LatidoCanal.objects.get(proceso="procesar_cobros").ciclos, 2)

    def test_envio_abandonado_queda_incierto_y_conserva_plaza(self):
        from datetime import timedelta

        from django.utils import timezone

        from pedidos.servicios.despacho import recuperar_intentos_abandonados
        from pedidos.servicios.intentos import plaza_ocupada

        self.assertTrue(self.solicitar().ok)
        intento = IntentoCobro.objects.get()
        IntentoCobro.objects.filter(pk=intento.pk).update(
            estado="enviando", envio_iniciado_en=timezone.now() - timedelta(seconds=61)
        )
        recuperar_intentos_abandonados()
        intento.refresh_from_db()
        self.assertEqual(intento.estado, "incierto")
        self.assertTrue(plaza_ocupada(self.comercio))

    def test_resolver_intento_sin_cobro_no_marca_pagado(self):
        from django.core.management import call_command
        from django.core.management.base import CommandError

        self.assertTrue(self.solicitar().ok)
        intento = IntentoCobro.objects.get()
        puerto = PuertoPeyFalso()
        puerto.fallar_con = ErrorPey("TIMEOUT", "timeout", puede_haberse_creado=True)
        enviar_intento(intento.pk, puerto)
        with self.assertRaises(CommandError):
            call_command(
                "resolver_intento", intento=str(intento.pk), accion="sin_cobro"
            )
        call_command(
            "resolver_intento",
            intento=str(intento.pk),
            accion="sin_cobro",
            confirmar=True,
        )
        intento.refresh_from_db()
        self.assertEqual(intento.estado, "rechazado")
        self.assertIsNone(intento.cobro_id)

    def test_comando_procesar_cobros_una_vez(self):
        from unittest.mock import patch

        from django.core.management import call_command

        with (
            patch(
                "pedidos.management.commands.procesar_cobros.modo_adaptador",
                return_value="desarrollo",
            ),
            patch("pedidos.management.commands.procesar_cobros.ciclo") as ciclo,
        ):
            call_command("procesar_cobros", una_vez=True)
        ciclo.assert_called_once()
        self.assertFalse(ciclo.call_args.kwargs["detener"]())

    def test_reserva_congela_edicion(self):
        from pedidos.contratos.v1 import CodigoError
        from pedidos.errores import ErrorNucleo
        from pedidos.models import Pedido
        from pedidos.servicios.intentos import exigir_editable

        self.assertTrue(self.solicitar().ok)
        pedido = Pedido.objects.get(pk=self.pedido.id)
        with self.assertRaises(ErrorNucleo) as error:
            exigir_editable(self.comercio, pedido)
        self.assertEqual(error.exception.codigo, CodigoError.PEDIDO_CONGELADO)
        self.assertEqual(IntentoCobro.objects.get().estado, "reservado")

    def test_compuerta_cerrada_no_reclama_reserva(self):
        self.assertTrue(self.solicitar().ok)
        intento = IntentoCobro.objects.get()
        puerto = PuertoPeyFalso()
        with override_settings(PEDIDOS_COBRO_HABILITADO=False):
            enviar_intento(intento.pk, puerto)
        intento.refresh_from_db()
        self.assertEqual(intento.estado, "reservado")
        self.assertEqual(puerto.llamadas, [])

    def test_error_inesperado_es_incierto_sin_fallback(self):
        self.assertTrue(self.solicitar().ok)
        intento = IntentoCobro.objects.get()
        puerto = PuertoPeyFalso()
        puerto.fallar_con = ValueError("respuesta ilegible")
        self.assertEqual(enviar_intento(intento.pk, puerto).estado, "incierto")
        self.assertEqual([llamada[0] for llamada in puerto.llamadas], ["qr"])
        enviar_intento(intento.pk, puerto)
        self.assertEqual(len(puerto.llamadas), 1)

    def test_caida_de_bd_tras_envio_conserva_plaza_y_no_reenvia(self):
        from unittest.mock import patch

        from django.db import OperationalError

        from pedidos.servicios.intentos import plaza_ocupada

        self.assertTrue(self.solicitar().ok)
        intento = IntentoCobro.objects.get()
        puerto = PuertoPeyFalso()
        with patch(
            "pedidos.servicios.despacho.Cobro.objects.create",
            side_effect=OperationalError("base caída"),
        ):
            with self.assertRaises(OperationalError):
                enviar_intento(intento.pk, puerto)
        intento.refresh_from_db()
        self.assertEqual(intento.estado, "enviando")
        self.assertTrue(plaza_ocupada(self.comercio))
        enviar_intento(intento.pk, puerto)
        self.assertEqual(len(puerto.llamadas), 1)

    def test_resolver_enlaza_id_sin_confirmar_pago(self):
        from django.core.management import call_command
        from movimientos.models import Movimiento

        self.assertTrue(self.solicitar().ok)
        intento = IntentoCobro.objects.get()
        puerto = PuertoPeyFalso()
        puerto.fallar_con = ErrorPey("TIMEOUT", "timeout", puede_haberse_creado=True)
        enviar_intento(intento.pk, puerto)
        call_command(
            "resolver_intento",
            intento=str(intento.pk),
            accion="enlazar",
            qr_id="identificador",
            confirmar=True,
        )
        intento.refresh_from_db()
        self.assertEqual(intento.estado, "pendiente")
        self.assertEqual(intento.cobro.pey_qr_id, "identificador")
        self.assertEqual(intento.cobro.qr_string, "")
        self.assertEqual(
            Movimiento.objects.get(cobro=intento.cobro).estado, "pendiente"
        )

    def test_otro_telefono_no_modifica_notificacion_pendiente(self):
        respuesta = self.solicitar(
            canal="notificacion", telefono_bancario_confirmado="1234567890"
        )
        self.assertTrue(respuesta.ok, respuesta.error)
        intento = IntentoCobro.objects.get()
        puerto = PuertoPeyFalso()
        enviar_intento(intento.pk, puerto)
        intento.refresh_from_db()
        self.assertEqual(intento.telefono_bancario, "")
        otra = self.solicitar(
            "otra", canal="notificacion", telefono_bancario_confirmado="1234567891"
        )
        self.assertFalse(otra.ok)
        self.assertEqual(otra.error.code.value, "INTENCION_DISTINTA")
        intento.refresh_from_db()
        self.assertEqual(intento.estado, "pendiente")
        self.assertEqual(len(puerto.llamadas), 1)

    def test_cambio_politica_permite_nueva_cotizacion_y_aceptacion(self):
        self.assertTrue(self.solicitar().ok)
        anterior = IntentoCobro.objects.get()
        puerto = PuertoPeyFalso()
        from unittest.mock import patch
        from config import modo

        with patch.object(modo, "POLITICA_NORMAL", "normal-2"):
            enviar_intento(anterior.pk, puerto)
            nueva_cotizacion = self.cotizar(self.ctx, self.pedido)
            datos = self.datos_aceptacion(self.ctx, nueva_cotizacion)
            mensaje, _ = self.driver.agregar_mensaje(
                self.ctx,
                "aceptar-nueva",
                3,
                "ACEPTAR " + nueva_cotizacion.cotizacion.token_resumen,
            )
            datos.update(command_key="aceptar-nueva", mensaje_consentimiento_id=mensaje)
            aceptado = self.nucleo.aceptar_cotizacion(self.ctx, **datos)
            self.assertTrue(aceptado.ok, aceptado.error)
            pedido = aceptado.data["pedido"]
            resultado = self.nucleo.solicitar_cobro(
                self.ctx,
                contrato_version="1.0",
                command_key="cobro-nuevo",
                pedido_id=pedido.id,
                expected_version=pedido.version,
                aceptacion_id=pedido.aceptacion.id,
                canal="qr_venta",
            )
            self.assertTrue(resultado.ok, resultado.error)
        anterior.refresh_from_db()
        self.assertEqual(anterior.estado, "descartado")
        self.assertEqual(IntentoCobro.objects.filter(estado="reservado").count(), 1)
        self.assertEqual(puerto.llamadas, [])

    def test_worker_produccion_exige_llave_antes_del_ciclo(self):
        from unittest.mock import patch

        from django.core.management import call_command
        from django.core.management.base import CommandError

        with (
            override_settings(PEY_API_KEY=""),
            patch(
                "pedidos.management.commands.procesar_cobros.modo_adaptador",
                return_value="produccion",
            ),
            patch("pedidos.management.commands.procesar_cobros.ciclo") as ciclo,
        ):
            with self.assertRaises(CommandError):
                call_command("procesar_cobros", una_vez=True)
        ciclo.assert_not_called()

    def test_vencimiento_y_evento_son_atomicos(self):
        from unittest.mock import patch

        from movimientos.models import Movimiento

        from pedidos.models import EventoPedido
        from pedidos.servicios.cobros import vencer_intento

        self.assertTrue(self.solicitar().ok)
        intento = IntentoCobro.objects.get()
        enviar_intento(intento.pk, PuertoPeyFalso())
        intento.refresh_from_db()
        movimiento = Movimiento.objects.get(cobro=intento.cobro)
        with patch(
            "pedidos.servicios.cobros.emitir", side_effect=RuntimeError("evento")
        ):
            with self.assertRaises(RuntimeError):
                vencer_intento(movimiento)
        movimiento.refresh_from_db()
        intento.refresh_from_db()
        self.assertEqual(movimiento.estado, "pendiente")
        self.assertEqual(intento.estado, "pendiente")
        vencer_intento(movimiento)
        movimiento.refresh_from_db()
        intento.refresh_from_db()
        self.assertEqual(movimiento.estado, "vencido")
        self.assertEqual(intento.estado, "vencido")
        self.assertEqual(
            EventoPedido.objects.filter(intento=intento, tipo="cobro.vencido").count(),
            1,
        )

    def test_crash_en_red_no_libera_plaza_ni_reenvia(self):
        from pedidos.servicios.intentos import plaza_ocupada

        self.assertTrue(self.solicitar().ok)
        intento = IntentoCobro.objects.get()
        puerto = PuertoPeyFalso()
        puerto.fallar_con = SystemExit("proceso terminado")
        with self.assertRaises(SystemExit):
            enviar_intento(intento.pk, puerto)
        intento.refresh_from_db()
        self.assertEqual(intento.estado, "enviando")
        self.assertTrue(plaza_ocupada(self.comercio))
        enviar_intento(intento.pk, puerto)
        self.assertEqual(len(puerto.llamadas), 1)

    def test_notificacion_incierta_no_hace_fallback_a_qr(self):
        resultado = self.solicitar(
            canal="notificacion", telefono_bancario_confirmado="1234567890"
        )
        self.assertTrue(resultado.ok, resultado.error)
        intento = IntentoCobro.objects.get()
        puerto = PuertoPeyFalso()
        puerto.fallar_con = ErrorPey("NO_DISPONIBLE", "5xx", puede_haberse_creado=True)
        self.assertEqual(enviar_intento(intento.pk, puerto).estado, "incierto")
        enviar_intento(intento.pk, puerto)
        self.assertEqual([tipo for tipo, _ in puerto.llamadas], ["notificacion"])

    def reservar_y_sincronizar(self, canal, codi_status, clabe=None):
        cambios = {"canal": canal}
        if canal == "notificacion":
            cambios["telefono_bancario_confirmado"] = "5512345678"
        self.assertTrue(self.solicitar(**cambios).ok)
        intento = IntentoCobro.objects.get()
        cuenta = intento.cuenta
        cuerpo = json.dumps(
            {
                "id": cuenta.pey_bank_account_id,
                "clabe": clabe or cuenta.clabe,
                "codiStatus": codi_status,
            }
        ).encode()
        with override_settings(PEY_API_KEY="prueba"):
            sincronizar(cuenta, transporte=lambda *args: (200, cuerpo))
        return intento, cuenta

    def assert_envio_bloqueado(self, intento, cuenta, anomalia):
        cuenta.refresh_from_db()
        self.assertEqual((cuenta.codi_status, cuenta.anomalia), ("pending", anomalia))
        campos = [
            "estado",
            "version",
            "cuenta_id",
            "pey_bank_account_id",
            "importe_efectivo_centavos",
            "canal",
            "telefono_bancario",
            "token_envio",
            "cobro_id",
        ]
        antes = IntentoCobro.objects.filter(pk=intento.pk).values(*campos).get()
        otra = crear_cuenta(self.comercio)
        puerto = PuertoPeyFalso()
        enviado = enviar_intento(intento.pk, puerto)
        self.assertEqual(enviado.estado, "reservado")
        self.assertEqual(puerto.llamadas, [])
        self.assertEqual(Cobro.objects.count(), 0)
        self.assertEqual(Movimiento.objects.count(), 0)
        despues = IntentoCobro.objects.filter(pk=intento.pk).values(*campos).get()
        self.assertEqual(despues, antes)
        self.assertEqual(despues["cuenta_id"], cuenta.pk)
        self.assertNotEqual(despues["pey_bank_account_id"], otra.pey_bank_account_id)

    def test_qr_no_envia_si_la_cuenta_quedo_pending(self):
        intento, cuenta = self.reservar_y_sincronizar("qr_venta", "PENDING")
        self.assert_envio_bloqueado(intento, cuenta, "")

    def test_push_no_envia_si_la_cuenta_quedo_pending(self):
        intento, cuenta = self.reservar_y_sincronizar("notificacion", "PENDING")
        self.assert_envio_bloqueado(intento, cuenta, "")

    def test_qr_no_envia_si_la_clabe_no_coincide(self):
        intento, cuenta = self.reservar_y_sincronizar(
            "qr_venta", "ACTIVE", clabe_valida(99)
        )
        self.assert_envio_bloqueado(intento, cuenta, "CLABE_NO_COINCIDE")

    def test_push_no_envia_si_la_clabe_no_coincide(self):
        intento, cuenta = self.reservar_y_sincronizar(
            "notificacion", "ACTIVE", clabe_valida(99)
        )
        self.assert_envio_bloqueado(intento, cuenta, "CLABE_NO_COINCIDE")

    def test_carrera_sync_confirmada_antes_del_claim_no_envia(self):
        self.assertTrue(self.solicitar().ok)
        intento = IntentoCobro.objects.get()
        cuenta = intento.cuenta
        cuerpo = json.dumps(
            {
                "id": cuenta.pey_bank_account_id,
                "clabe": cuenta.clabe,
                "codiStatus": "PENDING",
            }
        ).encode()
        dentro, seguir = Event(), Event()
        puerto = PuertoPeyFalso()

        bloqueos = 0

        def bloquear(cuenta):
            nonlocal bloqueos
            cuenta = bloquear_cuenta(cuenta)
            bloqueos += 1
            if bloqueos == 2:  # _aplicar, después de consultar pey
                dentro.set()
                seguir.wait(10)
            return cuenta

        def en_hilo(funcion):
            close_old_connections()
            try:
                return funcion()
            finally:
                connections.close_all()

        with (
            override_settings(PEY_API_KEY="prueba"),
            patch("ambito.operaciones_cuenta.bloquear_cuenta", side_effect=bloquear),
            ThreadPoolExecutor(max_workers=2) as pool,
        ):
            sync = pool.submit(
                en_hilo,
                lambda: sincronizar(cuenta, transporte=lambda *args: (200, cuerpo)),
            )
            try:
                self.assertTrue(dentro.wait(10))
                envio = pool.submit(en_hilo, lambda: enviar_intento(intento.pk, puerto))
                esperar([envio], timeout=1)
                bloqueado = not envio.done()
            finally:
                seguir.set()
            sync.result(10)
            enviado = envio.result(10)
        self.assertTrue(bloqueado)
        cuenta.refresh_from_db()
        self.assertEqual(cuenta.codi_status, "pending")
        self.assertEqual(enviado.estado, "reservado")
        self.assertEqual(puerto.llamadas, [])
        self.assertEqual(Cobro.objects.count(), 0)
