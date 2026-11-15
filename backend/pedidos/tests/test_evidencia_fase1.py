"""La evidencia muestra relaciones sin publicar datos sensibles."""

import json
from io import StringIO
from uuid import uuid4

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test.utils import CaptureQueriesContext

from ambito.tests.soporte import crear_cuenta
from canales.models import ConversacionCanal, MensajeEntrante, SesionCanal
from movimientos.models import Cobro, Movimiento
from pedidos.models import IntentoCobro, Pedido
from pedidos.tests.soporte_real import CasoReal
from webhooks.models import AvisoRecibido


class EvidenciaFase1Tests(CasoReal):
    def setUp(self):
        super().setUp()
        ctx, _, pedido = self.crear()
        pedido = self.cotizar(ctx, pedido)
        self.nucleo.aceptar_cotizacion(ctx, **self.datos_aceptacion(ctx, pedido))
        self.pedido_id = pedido.id
        self.comercio = self.driver._comercio("comercio")

    def salida(self):
        salida = StringIO()
        call_command("evidencia_fase1", pedido=str(self.pedido_id), stdout=salida)
        return salida.getvalue()

    def test_cadena_vacia_y_solo_lectura(self):
        with CaptureQueriesContext(connection) as consultas:
            datos = json.loads(self.salida())
        self.assertEqual(datos["pedido"]["id"], str(self.pedido_id))
        self.assertEqual(len(datos["revisiones"]), 1)
        self.assertEqual(len(datos["aceptaciones"]), 1)
        self.assertEqual(datos["intentos"], [])
        self.assertIsNone(datos["mensaje"])
        self.assertTrue(datos["eventos"])
        self.assertTrue(
            all(q["sql"].lstrip().upper().startswith("SELECT") for q in consultas)
        )

    def test_cadena_completa_no_expone_clabe_telefono_ni_cuerpos(self):
        cuenta = crear_cuenta(self.comercio)
        aceptacion = self.comercio.aceptacion_set.get()
        cobro = Cobro.objects.create(
            comercio=self.comercio,
            cuenta=cuenta,
            canal="notificacion",
            monto="1.00",
            concepto="contenido privado",
            pey_transaction_id="tx-prueba",
        )
        movimiento = Movimiento.objects.create(
            comercio=self.comercio,
            cobro=cobro,
            canal="notificacion",
            monto="1.00",
            concepto="contenido privado",
            estado="pendiente",
            origen="origen_pey",
        )
        AvisoRecibido.objects.create(
            webhook_id="aviso-5512345678", movimiento=movimiento, resultado="aplicado"
        )
        intento = IntentoCobro.objects.create(
            origen="pedido",
            comercio=self.comercio,
            pedido_id=self.pedido_id,
            aceptacion=aceptacion,
            cotizacion=aceptacion.cotizacion,
            canal="notificacion",
            estado="pendiente",
            importe_efectivo_centavos=100,
            demo_mode=False,
            politica_cobro_version="normal-1",
            cuenta=cuenta,
            pey_bank_account_id=cuenta.pey_bank_account_id,
            concepto="contenido privado",
            expiracion_s=600,
            telefono_bancario="5512345678",
            cobro=cobro,
        )
        texto = self.salida()
        datos = json.loads(texto)
        cadena = datos["intentos"][0]
        self.assertEqual(cadena["id"], str(intento.pk))
        self.assertEqual(
            cadena["cuenta"]["clabe_enmascarada"], "***" + cuenta.clabe[-4:]
        )
        self.assertEqual(cadena["cobro"]["id"], cobro.pk)
        self.assertEqual(cadena["cobro"]["movimientos"][0]["id"], movimiento.pk)
        self.assertEqual(
            cadena["cobro"]["movimientos"][0]["avisos"][0]["webhook_id"],
            "[identificador omitido]",
        )
        self.assertNotIn(cuenta.clabe, texto)
        self.assertNotIn("5512345678", texto)
        self.assertNotIn("contenido privado", texto)

    def test_mensaje_persistido_muestra_estado_sin_contenido(self):
        pedido = Pedido.objects.get(pk=self.pedido_id)
        sesion = SesionCanal.objects.create(
            comercio=self.comercio, instancia_id="instancia", sesion_id="sesion"
        )
        conversacion = ConversacionCanal.objects.create(
            sesion=sesion, chat_id="5512345678", cliente_externo_id="5512345678"
        )
        MensajeEntrante.objects.create(
            id=pedido.mensaje_origen_id,
            conversacion=conversacion,
            instancia_id="instancia",
            sesion_id="sesion",
            id_mensaje_proveedor="id",
            hash_payload="hash",
            secuencia=1,
            tipo="texto",
            texto="contenido privado",
        )
        texto = self.salida()
        mensaje = json.loads(texto)["mensaje"]
        self.assertEqual(mensaje["id"], str(pedido.mensaje_origen_id))
        self.assertEqual(mensaje["estado"], "pendiente")
        self.assertTrue(mensaje["recibido_en"])
        self.assertNotIn("5512345678", texto)
        self.assertNotIn("contenido privado", texto)

    def test_pedido_invalido_o_inexistente(self):
        for identificador in ("incorrecto", str(uuid4())):
            with (
                self.subTest(identificador=identificador),
                self.assertRaises(CommandError),
            ):
                call_command("evidencia_fase1", pedido=identificador, stdout=StringIO())
