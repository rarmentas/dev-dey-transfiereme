from pedidos.tests.test_pedido_api import PedidoApiTests


class RenglonesApiTests(PedidoApiTests):
    def test_revision_valida_idempotencia_y_rechaza_total(self):
        url = f"/api/pedidos/{self.pedido.id}/renglones/"
        datos = {
            "command_key": "revision",
            "expected_version": 1,
            "renglones": [
                {
                    "renglon_id": self.pedido.renglones[0].renglon_id,
                    "descripcion": "Leche",
                    "cantidad": "1.250",
                    "unidad": "litro",
                    "precio_unitario_centavos": 101,
                    "resolucion": "incluido",
                    "motivo_exclusion": "",
                }
            ],
        }
        invalido = {**datos, "total_comercial_centavos": 1}
        self.assertEqual(
            self.client.put(url, invalido, content_type="application/json").status_code,
            400,
        )
        respuesta = self.client.put(url, datos, content_type="application/json")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["data"]["version"], 2)
        self.assertTrue(
            self.client.put(url, datos, content_type="application/json").json()[
                "replayed"
            ]
        )
        datos["renglones"][0]["precio_unitario_centavos"] = 200
        self.assertEqual(
            self.client.put(url, datos, content_type="application/json").json()[
                "codigo"
            ],
            "CLAVE_REUTILIZADA",
        )

    def test_incluido_incompleto_y_renglones_ajenos(self):
        url = f"/api/pedidos/{self.pedido.id}/renglones/"
        datos = {
            "command_key": "revision",
            "expected_version": 1,
            "renglones": [
                {
                    "renglon_id": self.pedido.renglones[0].renglon_id,
                    "resolucion": "incluido",
                }
            ],
        }
        respuesta = self.client.put(url, datos, content_type="application/json")
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn(
            "renglones.0.precio_unitario_centavos", respuesta.json()["errores"]
        )
        datos["renglones"] = []
        self.assertEqual(
            self.client.put(url, datos, content_type="application/json").status_code,
            400,
        )

    def test_editar_invalida_cotizacion_y_aceptacion(self):
        pedido = self.cotizar(self.ctx, self.pedido)
        datos = self.datos_aceptacion(self.ctx, pedido)
        aceptado = self.nucleo.aceptar_cotizacion(self.ctx, **datos).data["pedido"]
        revision = {
            "command_key": "editar",
            "expected_version": aceptado.version,
            "renglones": [
                {
                    "renglon_id": aceptado.renglones[0].renglon_id,
                    "descripcion": "Nueva leche",
                    "cantidad": "1",
                    "unidad": "pieza",
                    "precio_unitario_centavos": 500,
                    "resolucion": "incluido",
                }
            ],
        }
        respuesta = self.client.put(
            f"/api/pedidos/{pedido.id}/renglones/",
            revision,
            content_type="application/json",
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertIsNone(respuesta.json()["data"]["cotizacion"])
        self.assertIsNone(respuesta.json()["data"]["aceptacion"])
        datos["command_key"] = "nuevo-intento"
        self.assertEqual(
            self.nucleo.aceptar_cotizacion(self.ctx, **datos).error.code.value,
            "REVISION_OBSOLETA",
        )
