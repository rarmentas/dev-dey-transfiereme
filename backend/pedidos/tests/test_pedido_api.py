from django.contrib.auth import get_user_model
from django.test import Client

from ambito.models import Comercio, Membresia
from pedidos.tests.soporte_real import CasoReal


class PedidoApiTests(CasoReal):
    def setUp(self):
        super().setUp()
        self.ctx, _, self.pedido = self.crear()
        self.comercio = Comercio.objects.get(pk=self.lector.resolver_comercio(self.ctx))
        self.usuario = get_user_model().objects.create_user(
            username="vendedor", password="clave"
        )
        Membresia.objects.create(usuario=self.usuario, comercio=self.comercio)
        self.client.force_login(self.usuario)

    def test_lista_detalle_vacio_y_ajeno(self):
        lista = self.client.get("/api/pedidos/")
        self.assertEqual(lista.status_code, 200)
        self.assertEqual(lista.json()["data"]["pedidos"][0]["id"], self.pedido.id)
        detalle = self.client.get(f"/api/pedidos/{self.pedido.id}/")
        self.assertEqual(
            detalle.json()["data"]["renglones"][0]["texto_solicitado"], "leche"
        )
        self.assertEqual(
            self.client.get("/api/pedidos/no-es-uuid/").json()["codigo"],
            "PEDIDO_NO_ACCESIBLE",
        )
        self.assertEqual(
            self.client.get("/api/pedidos/?comercio_id=1").status_code, 400
        )
        otro = get_user_model().objects.create_user(username="otro")
        Membresia.objects.create(
            usuario=otro, comercio=Comercio.objects.create(nombre="Otro")
        )
        self.client.force_login(otro)
        self.assertEqual(self.client.get("/api/pedidos/").json()["data"]["pedidos"], [])
        self.assertEqual(
            self.client.get(f"/api/pedidos/{self.pedido.id}/").status_code, 404
        )

    def test_csrf_es_obligatorio(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.usuario)
        respuesta = cliente.post(
            f"/api/pedidos/{self.pedido.id}/cotizaciones/",
            {"command_key": "x", "expected_version": 1},
            content_type="application/json",
        )
        self.assertEqual(respuesta.status_code, 403)
        self.assertIn("CSRF", respuesta.json()["detail"])
