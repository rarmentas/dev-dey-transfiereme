"""La edición de una espera conserva el feed de eventos consecutivo."""

from ambito.tests.soporte import crear_cuenta
from django.test import override_settings

from pedidos.contratos.fixtures import id_determinista
from pedidos.contratos.v1 import RenglonSolicitadoV1
from pedidos.models import EventoPedido, IntentoCobro, Pedido
from pedidos.servicios.tendero import operar
from pedidos.tests.soporte_real import CasoReal


@override_settings(PEDIDOS_COBRO_HABILITADO=True)
class EsperaEditableTests(CasoReal):
    def preparar_espera(self):
        comercio = self.driver._comercio("comercio")
        cuenta = crear_cuenta(comercio)
        IntentoCobro.objects.create(
            origen="legado",
            comercio=comercio,
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
        ctx, _, pedido = self.crear("-b")
        pedido = self.cotizar(ctx, pedido)
        datos = self.datos_aceptacion(ctx, pedido)
        aceptado = self.nucleo.aceptar_cotizacion(ctx, **datos).data["pedido"]
        resultado = self.nucleo.solicitar_cobro(
            ctx,
            contrato_version="1.0",
            command_key="espera",
            pedido_id=pedido.id,
            expected_version=aceptado.version,
            aceptacion_id=aceptado.aceptacion.id,
            canal="qr_venta",
        )
        self.assertTrue(resultado.ok, resultado.error)
        espera = resultado.data["pedido"]
        self.assertEqual(espera.pago_estado.value, "en_espera")
        return comercio, ctx, espera

    def verificar_eventos(self, comercio, pedido_id):
        intento = IntentoCobro.objects.get(pedido_id=pedido_id)
        self.assertEqual(intento.estado, "descartado")
        secuencias = list(
            EventoPedido.objects.filter(comercio=comercio)
            .order_by("secuencia_comercio")
            .values_list("secuencia_comercio", flat=True)
        )
        self.assertEqual(secuencias, list(range(1, len(secuencias) + 1)))
        self.assertEqual(
            EventoPedido.objects.filter(
                pedido_id=pedido_id, tipo="cobro.descartado"
            ).count(),
            1,
        )

    def test_i7_corregir_espera_descarta_y_conserva_revision_y_secuencia(self):
        comercio, ctx, espera = self.preparar_espera()
        mensaje, llave = self.driver.agregar_mensaje(ctx, "correccion", 3, "pan")
        resultado = self.nucleo.corregir_borrador(
            ctx,
            contrato_version="1.0",
            command_key="corregir",
            pedido_id=espera.id,
            expected_version=espera.version,
            mensaje_id=mensaje,
            message_key=llave,
            secuencia_conversacion=3,
            renglones=[RenglonSolicitadoV1(id_determinista("i7", "pan"), "pan")],
        )
        self.assertTrue(resultado.ok, resultado.error)
        self.assertEqual(Pedido.objects.get(pk=espera.id).estado, "en_revision")
        self.verificar_eventos(comercio, espera.id)

    def test_i7_tendero_publica_espera_y_secuencia_consecutiva(self):
        comercio, _, espera = self.preparar_espera()
        resultado = operar(
            comercio,
            espera.id,
            "publicar_cotizacion",
            {"command_key": "republicar", "expected_version": espera.version},
        )
        self.assertTrue(resultado.ok)
        self.assertEqual(Pedido.objects.get(pk=espera.id).estado, "cotizado")
        self.verificar_eventos(comercio, espera.id)
