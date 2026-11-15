from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from ambito.models import Comercio, Membresia
from movimientos.models import Cobro, Movimiento
from pedidos.models import IntentoCobro


class ModoDemoTests(TestCase):
    def setUp(self):
        usuario = get_user_model().objects.create_user(username="demo")
        Membresia.objects.create(
            usuario=usuario,
            comercio=Comercio.objects.create(nombre="Demo", es_demo=True),
        )
        self.client.force_login(usuario)

    def test_rutas_legacy_bloqueadas_sin_efectos(self):
        with (
            patch("ventas.views.crear_venta_qr") as qr,
            patch("ventas.views.crear_venta_notificacion") as notificacion,
            patch("movimientos.views_cobro.alta_qr_general") as general,
            patch("pedidos.servicios.despacho.obtener_puerto") as puerto_venta,
            patch("movimientos.alta_qr_general.obtener_puerto") as puerto_general,
        ):
            for url in (
                "/api/ventas/",
                "/api/ventas/notificacion/",
                "/api/cobro/qr-general/",
            ):
                respuesta = self.client.post(url, {}, content_type="application/json")
                self.assertEqual(respuesta.status_code, 403)
                self.assertEqual(respuesta.json()["codigo"], "RUTA_BLOQUEADA_EN_DEMO")
                self.assertNotEqual(respuesta.json()["detail"], "Debe iniciar sesión.")
                con_datos = self.client.post(
                    url, {"monto": "25.00", "telefono": "1234567890"},
                    content_type="application/json", HTTP_IDEMPOTENCY_KEY="clave",
                )
                self.assertEqual(con_datos.status_code, 403)
                self.assertEqual(con_datos.json()["codigo"], "RUTA_BLOQUEADA_EN_DEMO")
            qr.assert_not_called()
            notificacion.assert_not_called()
            general.assert_not_called()
            puerto_venta.assert_not_called()
            puerto_general.assert_not_called()
        self.assertEqual(Cobro.objects.count(), 0)
        self.assertEqual(Movimiento.objects.count(), 0)
        self.assertEqual(IntentoCobro.objects.count(), 0)
