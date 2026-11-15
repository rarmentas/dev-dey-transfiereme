from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from ambito.models import Comercio, Membresia
from movimientos.models import Cobro, Movimiento


class ModoDemoTests(TestCase):
    def setUp(self):
        usuario = get_user_model().objects.create_user(username="demo")
        Membresia.objects.create(
            usuario=usuario, comercio=Comercio.objects.create(nombre="Demo")
        )
        self.client.force_login(usuario)

    @override_settings(DEMO_MODE="true")
    def test_rutas_legacy_bloqueadas_sin_efectos(self):
        with (
            patch("ventas.views.crear_venta_qr") as qr,
            patch("ventas.views.crear_venta_notificacion") as notificacion,
            patch("movimientos.views_cobro.alta_qr_general") as general,
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
            qr.assert_not_called()
            notificacion.assert_not_called()
            general.assert_not_called()
        self.assertEqual(Cobro.objects.count(), 0)
        self.assertEqual(Movimiento.objects.count(), 0)
