from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.db import close_old_connections

from pedidos.contratos.v1 import CodigoError
from pedidos.models import ComandoNucleo, EventoPedido, Pedido
from pedidos.tests.soporte_real import CasoReal


class IdempotenciaTests(CasoReal):
    def test_clave_distinto_payload_no_modifica(self):
        ctx, datos, pedido = self.crear()
        datos["secuencia_conversacion"] = 2
        mensaje, llave = self.driver.agregar_mensaje(ctx, "otro", 2, "pan")
        datos.update(mensaje_id=mensaje, message_key=llave)
        respuesta = self.nucleo.registrar_solicitud(ctx, **datos)
        self.assertEqual(respuesta.error.code, CodigoError.CLAVE_REUTILIZADA)
        self.assertEqual(Pedido.objects.count(), 1)
        self.assertEqual(EventoPedido.objects.count(), 1)
        self.assertEqual(ComandoNucleo.objects.count(), 1)
        self.assertEqual(Pedido.objects.get().id.hex, pedido.id.replace("-", ""))

    def test_reintentos_concurrentes_mismo_mensaje(self):
        ctx = self.driver.contexto()
        mensaje, llave = self.driver.agregar_mensaje(ctx, "solicitud", 1, "leche")
        from pedidos.contratos.fixtures import id_determinista
        from pedidos.contratos.v1 import RenglonSolicitadoV1

        datos = {
            "contrato_version": "1.0",
            "command_key": "crear",
            "mensaje_id": mensaje,
            "message_key": llave,
            "secuencia_conversacion": 1,
            "renglones": [
                RenglonSolicitadoV1(id_determinista("concurrente", "r"), "leche")
            ],
        }
        barrera = Barrier(2)

        def ejecutar():
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                return self.nucleo.registrar_solicitud(ctx, **datos)
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as ejecutor:
            respuestas = list(ejecutor.map(lambda _: ejecutar(), range(2)))
        self.assertTrue(all(r.ok for r in respuestas))
        self.assertEqual(sum(r.replayed for r in respuestas), 1)
        self.assertEqual(
            respuestas[0].data["pedido"].id, respuestas[1].data["pedido"].id
        )
        self.assertEqual(
            (
                Pedido.objects.count(),
                EventoPedido.objects.count(),
                ComandoNucleo.objects.count(),
            ),
            (1, 1, 1),
        )

    def test_secuencias_contiguas_bajo_concurrencia(self):
        from pedidos.contratos.fixtures import id_determinista
        from pedidos.contratos.v1 import RenglonSolicitadoV1

        contextos = [self.driver.contexto(str(i)) for i in range(4)]
        comandos = []
        for indice, ctx in enumerate(contextos):
            mensaje, llave = self.driver.agregar_mensaje(ctx, "solicitud", 1, "pan")
            comandos.append(
                {
                    "contrato_version": "1.0",
                    "command_key": f"crear-{indice}",
                    "mensaje_id": mensaje,
                    "message_key": llave,
                    "secuencia_conversacion": 1,
                    "renglones": [
                        RenglonSolicitadoV1(id_determinista(str(indice), "r"), "pan")
                    ],
                }
            )
        barrera = Barrier(4)

        def ejecutar(indice):
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                return self.nucleo.registrar_solicitud(
                    contextos[indice], **comandos[indice]
                )
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=4) as ejecutor:
            respuestas = list(ejecutor.map(ejecutar, range(4)))
        self.assertTrue(all(r.ok for r in respuestas), [r.error for r in respuestas])
        self.assertEqual(
            list(
                EventoPedido.objects.order_by("secuencia_comercio").values_list(
                    "secuencia_comercio", flat=True
                )
            ),
            [1, 2, 3, 4],
        )
        self.assertEqual(
            list(Pedido.objects.order_by("numero").values_list("numero", flat=True)),
            [1, 2, 3, 4],
        )

    def test_renglon_de_otro_pedido_no_puede_reasignarse(self):
        from pedidos.contratos.v1 import RenglonSolicitadoV1

        ctx, _, primero = self.crear("1")
        _, _, segundo = self.crear("2")
        mensaje, llave = self.driver.agregar_mensaje(ctx, "correccion", 2, "pan")
        respuesta = self.nucleo.corregir_borrador(
            ctx,
            contrato_version="1.0",
            command_key="corregir",
            pedido_id=primero.id,
            expected_version=primero.version,
            mensaje_id=mensaje,
            message_key=llave,
            secuencia_conversacion=2,
            renglones=[RenglonSolicitadoV1(segundo.renglones[0].renglon_id, "pan")],
        )
        self.assertEqual(respuesta.error.code, CodigoError.PAYLOAD_INVALIDO)
        self.assertEqual(Pedido.objects.get(pk=segundo.id).renglones.count(), 1)

    def test_validacion_no_consume_clave(self):
        ctx = self.driver.contexto()
        mensaje, llave = self.driver.agregar_mensaje(ctx, "solicitud", 1, "pan")
        from pedidos.contratos.fixtures import id_determinista
        from pedidos.contratos.v1 import RenglonSolicitadoV1

        datos = {
            "contrato_version": "1.0",
            "command_key": "crear",
            "mensaje_id": mensaje,
            "message_key": llave,
            "secuencia_conversacion": 1,
            "renglones": [],
        }
        self.assertEqual(
            self.nucleo.registrar_solicitud(ctx, **datos).error.code,
            CodigoError.PAYLOAD_INVALIDO,
        )
        self.assertFalse(ComandoNucleo.objects.exists())
        datos["renglones"] = [
            RenglonSolicitadoV1(id_determinista("valido", "r"), "pan")
        ]
        self.assertTrue(self.nucleo.registrar_solicitud(ctx, **datos).ok)
        self.assertEqual(ComandoNucleo.objects.count(), 1)

    def test_fallo_de_base_revierte_efecto_y_no_consume_clave(self):
        from unittest.mock import patch

        from django.db import OperationalError

        from pedidos.contratos.fixtures import id_determinista
        from pedidos.contratos.v1 import RenglonSolicitadoV1

        ctx = self.driver.contexto()
        mensaje, llave = self.driver.agregar_mensaje(ctx, "solicitud", 1, "pan")
        datos = {
            "contrato_version": "1.0",
            "command_key": "caida",
            "mensaje_id": mensaje,
            "message_key": llave,
            "secuencia_conversacion": 1,
            "renglones": [RenglonSolicitadoV1(id_determinista("caida", "r"), "pan")],
        }
        with patch(
            "pedidos.servicios.solicitudes.emitir",
            side_effect=OperationalError("fallo"),
        ):
            resultado = self.nucleo.registrar_solicitud(ctx, **datos)
        self.assertEqual(resultado.error.code, CodigoError.SERVICIO_NO_DISPONIBLE)
        self.assertTrue(resultado.error.retryable)
        self.assertEqual(Pedido.objects.count(), 0)
        self.assertEqual(ComandoNucleo.objects.count(), 0)
        self.assertTrue(self.nucleo.registrar_solicitud(ctx, **datos).ok)
