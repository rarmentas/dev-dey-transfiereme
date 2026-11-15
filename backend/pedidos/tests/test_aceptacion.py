from dataclasses import replace

from pedidos.contratos.v1 import CodigoError
from pedidos.models import Aceptacion
from pedidos.tests.soporte_real import CasoReal


class AceptacionTests(CasoReal):
    def test_consentimiento_debe_ser_texto_exacto_y_resumen_enviado(self):
        ctx, _, pedido = self.crear()
        pedido = self.cotizar(ctx, pedido)
        datos = self.datos_aceptacion(ctx, pedido)
        clave = (ctx, datos["mensaje_consentimiento_id"])
        original = self.lector.mensajes[clave]
        for texto, tipo in (
            ("sí", "texto"),
            ("ACEPTAR " + pedido.cotizacion.token_resumen + " extra", "texto"),
            ("ACEPTAR " + pedido.cotizacion.token_resumen, "audio"),
        ):
            self.lector.mensajes[clave] = replace(
                original, texto_normalizado=texto, tipo=tipo
            )
            self.assertEqual(
                self.nucleo.aceptar_cotizacion(ctx, **datos).error.code,
                CodigoError.ACEPTACION_REQUERIDA,
            )
        self.lector.mensajes[clave] = original
        resumen = self.lector.resumenes.pop((ctx, pedido.cotizacion.id))
        self.assertEqual(
            self.nucleo.aceptar_cotizacion(ctx, **datos).error.code,
            CodigoError.ACEPTACION_REQUERIDA,
        )
        self.lector.resumenes[(ctx, pedido.cotizacion.id)] = resumen
        self.assertTrue(self.nucleo.aceptar_cotizacion(ctx, **datos).ok)
        self.assertEqual(Aceptacion.objects.count(), 1)

    def test_importe_y_revision_obsoletos(self):
        ctx, _, pedido = self.crear()
        pedido = self.cotizar(ctx, pedido)
        datos = self.datos_aceptacion(ctx, pedido)
        datos["importe_efectivo_mostrado_centavos"] += 1
        self.assertEqual(
            self.nucleo.aceptar_cotizacion(ctx, **datos).error.code,
            CodigoError.IMPORTE_NO_COINCIDE,
        )
        datos["importe_efectivo_mostrado_centavos"] -= 1
        self.driver.invalidar_cotizacion(pedido.id)
        self.assertEqual(
            self.nucleo.aceptar_cotizacion(ctx, **datos).error.code,
            CodigoError.REVISION_OBSOLETA,
        )
        self.assertEqual(Aceptacion.objects.count(), 0)

    def test_replay_historico_no_autoriza_cobro_tras_invalidar(self):
        ctx, _, pedido = self.crear()
        pedido = self.cotizar(ctx, pedido)
        datos = self.datos_aceptacion(ctx, pedido)
        aceptado = self.nucleo.aceptar_cotizacion(ctx, **datos).data["pedido"]
        self.driver.invalidar_cotizacion(pedido.id)
        repetido = self.nucleo.aceptar_cotizacion(ctx, **datos)
        self.assertTrue(repetido.replayed)
        self.assertEqual(repetido.data["pedido"].aceptacion.id, aceptado.aceptacion.id)
        cobro = self.nucleo.solicitar_cobro(
            ctx,
            contrato_version="1.0",
            command_key="cobrar",
            pedido_id=pedido.id,
            expected_version=aceptado.version,
            aceptacion_id=aceptado.aceptacion.id,
            canal="qr_venta",
        )
        self.assertEqual(cobro.error.code, CodigoError.ACEPTACION_REQUERIDA)
        actual = self.nucleo.consultar_pedido(
            ctx, contrato_version="1.0", pedido_id=pedido.id
        )
        self.assertIsNone(actual.data["pedido"].aceptacion)

    def test_mensaje_de_otra_conversacion_no_autoriza(self):
        ctx, _, pedido = self.crear()
        pedido = self.cotizar(ctx, pedido)
        datos = self.datos_aceptacion(ctx, pedido)
        self.lector.mensajes.pop((ctx, datos["mensaje_consentimiento_id"]))
        respuesta = self.nucleo.aceptar_cotizacion(ctx, **datos)
        self.assertEqual(respuesta.error.code, CodigoError.CONTEXTO_INVALIDO)
        self.assertEqual(Aceptacion.objects.count(), 0)

    def test_carrera_entre_revision_y_aceptacion(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier

        from django.db import close_old_connections

        from pedidos.errores import ErrorNucleo
        from pedidos.servicios.tendero import operar

        ctx, _, pedido = self.crear()
        pedido = self.cotizar(ctx, pedido)
        datos = self.datos_aceptacion(ctx, pedido)
        comercio = self.driver.comercios["comercio"]
        revision = {
            "command_key": "revision-carrera",
            "expected_version": pedido.version,
            "renglones": [
                {
                    "renglon_id": pedido.renglones[0].renglon_id,
                    "descripcion": "pan",
                    "cantidad": "1",
                    "unidad": "pieza",
                    "precio_unitario_centavos": 100,
                    "resolucion": "incluido",
                    "motivo_exclusion": "",
                }
            ],
        }
        barrera = Barrier(2)

        def ejecutar(tipo):
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                if tipo == "aceptar":
                    resultado = self.nucleo.aceptar_cotizacion(ctx, **datos)
                    return (
                        resultado.ok,
                        resultado.error.code if resultado.error else None,
                    )
                try:
                    operar(comercio, pedido.id, "revisar_renglones", revision)
                    return True, None
                except ErrorNucleo as exc:
                    return False, exc.codigo
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as ejecutor:
            aceptacion, edicion = list(ejecutor.map(ejecutar, ["aceptar", "editar"]))
        self.assertEqual(sum([aceptacion[0], edicion[0]]), 1)
        if aceptacion[0]:
            self.assertEqual(edicion[1], CodigoError.VERSION_OBSOLETA)
            self.assertEqual(Aceptacion.objects.count(), 1)
        else:
            self.assertEqual(aceptacion[1], CodigoError.REVISION_OBSOLETA)
            self.assertEqual(Aceptacion.objects.count(), 0)
