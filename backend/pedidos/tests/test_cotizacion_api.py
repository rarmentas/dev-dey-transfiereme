from pedidos.tests.test_pedido_api import PedidoApiTests


class CotizacionApiTests(PedidoApiTests):
    def test_publica_solo_resuelta_y_redondea_en_servidor(self):
        url = f"/api/pedidos/{self.pedido.id}/cotizaciones/"
        datos = {"command_key": "publicar", "expected_version": 1}
        respuesta = self.client.post(url, datos, content_type="application/json")
        self.assertEqual(respuesta.status_code, 409)
        self.assertEqual(respuesta.json()["codigo"], "RENGLON_PENDIENTE")
        revision = {
            "command_key": "revisar",
            "expected_version": 1,
            "renglones": [
                {
                    "renglon_id": self.pedido.renglones[0].renglon_id,
                    "descripcion": "Leche",
                    "cantidad": "1.005",
                    "unidad": "l",
                    "precio_unitario_centavos": 100,
                    "resolucion": "incluido",
                }
            ],
        }
        self.assertEqual(
            self.client.put(
                f"/api/pedidos/{self.pedido.id}/renglones/",
                revision,
                content_type="application/json",
            ).status_code,
            200,
        )
        datos["expected_version"] = 2
        respuesta = self.client.post(url, datos, content_type="application/json")
        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(
            respuesta.json()["data"]["cotizacion"]["total_comercial_centavos"], 101
        )
        repeticion = self.client.post(url, datos, content_type="application/json")
        self.assertEqual(repeticion.status_code, 200)
        self.assertTrue(repeticion.json()["replayed"])

    def test_subtotal_cero_puede_revisarse_pero_no_publicarse(self):
        revision = {
            "command_key": "revision-cero",
            "expected_version": 1,
            "renglones": [
                {
                    "renglon_id": self.pedido.renglones[0].renglon_id,
                    "descripcion": "Un gramo",
                    "cantidad": "0.001",
                    "precio_unitario_centavos": 1,
                    "resolucion": "incluido",
                }
            ],
        }
        respuesta = self.client.put(
            f"/api/pedidos/{self.pedido.id}/renglones/",
            revision,
            content_type="application/json",
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(
            respuesta.json()["data"]["renglones"][0]["subtotal_centavos"], 0
        )
        respuesta = self.client.post(
            f"/api/pedidos/{self.pedido.id}/cotizaciones/",
            {"command_key": "publicar-cero", "expected_version": 2},
            content_type="application/json",
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(respuesta.json()["codigo"], "PAYLOAD_INVALIDO")
