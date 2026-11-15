import uuid

from django.db import IntegrityError, transaction
from django.test import TestCase

from ambito.models import Comercio
from pedidos.models import Pedido, RenglonPedido


class ModelosTests(TestCase):
    def setUp(self) -> None:
        self.comercio = Comercio.objects.create(nombre="Tienda")
        self.datos = {
            "comercio": self.comercio,
            "numero": 1,
            "instancia_id": "instancia",
            "sesion_id": "sesion",
            "conversacion_id": "conversacion",
            "cliente_externo_id": "cliente",
            "mensaje_origen_id": uuid.uuid4(),
            "message_key_origen": "mensaje",
            "secuencia_conversacion_aplicada": 1,
        }

    def test_un_solo_pedido_abierto_por_conversacion(self) -> None:
        Pedido.objects.create(**self.datos)
        self.datos.update(numero=2, mensaje_origen_id=uuid.uuid4())
        with self.assertRaises(IntegrityError), transaction.atomic():
            Pedido.objects.create(**self.datos)
        self.datos.update(estado="cerrado", abierto=False)
        self.assertFalse(Pedido.objects.create(**self.datos).abierto)

    def test_incluido_necesita_precio_cantidad_y_descripcion(self) -> None:
        pedido = Pedido.objects.create(**self.datos)
        with self.assertRaises(IntegrityError), transaction.atomic():
            RenglonPedido.objects.create(
                pedido=pedido, posicion=1, texto_solicitado="pan", resolucion="incluido"
            )
        renglon = RenglonPedido.objects.create(
            pedido=pedido,
            posicion=1,
            texto_solicitado="pan",
            resolucion="incluido",
            descripcion="Pan",
            cantidad="1",
            precio_unitario_centavos=100,
        )
        self.assertEqual(renglon.precio_unitario_centavos, 100)
