"""POST /api/cuenta/sincronizar/ — sync y rate limit."""

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from ambito.models import Comercio, Membresia
from pey.cuentas import CuentaPey
from pey.tipos import ErrorPey
from sesion.middleware import _MENSAJE_SIN_SESION

_CLABE = "012180015826225713"
_ULID = "01J9ZQ4C8X7Y6W5V4T3S2R1Q0P"
_RUTA = "/api/cuenta/pey/sincronizar/"


@override_settings(DEBUG=True, PEY_ADAPTADOR="produccion", PEY_API_KEY="llave")
class SincronizarCuentaApiTests(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.comercio = Comercio.objects.create(
            nombre="Tienda",
            clabe=_CLABE,
            pey_bank_account_id=_ULID,
        )
        self.usuario = User.objects.create_user(username="vend", password="pass")
        Membresia.objects.create(usuario=self.usuario, comercio=self.comercio)
        self.client.force_login(self.usuario)
        self.red = patch("urllib.request.urlopen", side_effect=AssertionError("red"))
        self.red.start()
        self.addCleanup(self.red.stop)

    def test_processing_pey_queda_paso_3(self) -> None:
        """Caso borde 10."""
        with patch(
            "integracion.pey.adaptador_produccion.consultar_cuenta",
            return_value=CuentaPey(id=_ULID, codi_status="PROCESSING"),
        ):
            respuesta = self.client.post(_RUTA)
        self.assertEqual(respuesta.status_code, 200)
        cuerpo = respuesta.json()
        self.assertEqual(cuerpo["paso"], 3)
        self.assertEqual(cuerpo["codi_status"], "pending")

    def test_not_found_limpia_id(self) -> None:
        """Caso borde 11."""
        with patch(
            "integracion.pey.adaptador_produccion.consultar_cuenta",
            side_effect=ErrorPey("BANK_ACCOUNT_NOT_FOUND", "no", "req-404"),
        ):
            respuesta = self.client.post(_RUTA)
        self.assertEqual(respuesta.status_code, 200)
        cuerpo = respuesta.json()
        self.assertEqual(cuerpo["paso"], 2)
        self.assertFalse(cuerpo["tiene_cuenta_pey"])
        self.comercio.refresh_from_db()
        self.assertEqual(self.comercio.pey_bank_account_id, "")

    def test_rate_limit_429(self) -> None:
        """Caso borde 12."""
        self.comercio.pey_codi_status_actualizado_en = timezone.now()
        self.comercio.save(update_fields=["pey_codi_status_actualizado_en"])
        respuesta = self.client.post(_RUTA)
        self.assertEqual(respuesta.status_code, 429)
        self.assertIn("reintento_en_segundos", respuesta.json())

    def test_tras_ventana_sync_permitido(self) -> None:
        self.comercio.pey_codi_status_actualizado_en = timezone.now() - timedelta(seconds=31)
        self.comercio.save(update_fields=["pey_codi_status_actualizado_en"])
        with patch(
            "integracion.pey.adaptador_produccion.consultar_cuenta",
            return_value=CuentaPey(id=_ULID, codi_status="ACTIVE", clabe=_CLABE),
        ):
            respuesta = self.client.post(_RUTA)
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.json()["puede_cobrar"])

    def test_error_pey_conserva_estado_200(self) -> None:
        self.comercio.pey_codi_status = Comercio.PeyCodiStatus.ACTIVE
        self.comercio.save()
        self.comercio.pey_codi_status_actualizado_en = timezone.now() - timedelta(seconds=60)
        self.comercio.save()
        with patch(
            "integracion.pey.adaptador_produccion.consultar_cuenta",
            side_effect=ErrorPey("NO_DISPONIBLE", "caído", "req-503"),
        ):
            respuesta = self.client.post(_RUTA)
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.json()["puede_cobrar"])

    def test_webhook_active_luego_sync(self) -> None:
        """Caso borde 5: ACTIVE persistido habilita cobro en GET."""
        self.comercio.pey_codi_status = Comercio.PeyCodiStatus.ACTIVE
        self.comercio.save()
        self.comercio.pey_codi_status_actualizado_en = timezone.now() - timedelta(seconds=60)
        self.comercio.save()
        respuesta = self.client.get("/api/cuenta/pey/estado/")
        self.assertTrue(respuesta.json()["puede_cobrar"])

    def test_misma_clabe_sync_restablece_active(self) -> None:
        """Caso borde 2."""
        self.comercio.pey_codi_status = Comercio.PeyCodiStatus.PENDING
        self.comercio.save()
        self.comercio.pey_codi_status_actualizado_en = timezone.now() - timedelta(seconds=60)
        self.comercio.save()
        with patch(
            "integracion.pey.adaptador_produccion.consultar_cuenta",
            return_value=CuentaPey(id=_ULID, codi_status="ACTIVE", clabe=_CLABE),
        ):
            respuesta = self.client.post(_RUTA)
        self.assertEqual(respuesta.json()["fase"], "activa")

    def test_sin_sesion_403(self) -> None:
        self.client.logout()
        respuesta = self.client.post(_RUTA)
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(respuesta.json()["detail"], _MENSAJE_SIN_SESION)

    def test_comercio_en_cuerpo_sincronizar_400(self) -> None:
        """Caso 14: sync rechaza comercio_id en el cuerpo."""
        self.comercio.pey_codi_status_actualizado_en = timezone.now() - timedelta(
            seconds=60
        )
        self.comercio.save()
        respuesta = self.client.post(
            _RUTA,
            {"comercio_id": 99},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("comercio", respuesta.json()["detail"].lower())

    def test_dos_sync_separados_por_ventana(self) -> None:
        """Caso borde 6: dos sync manuales válidos; el último save define el estado."""
        self.comercio.pey_codi_status_actualizado_en = timezone.now() - timedelta(
            seconds=60
        )
        self.comercio.save()
        with patch(
            "integracion.pey.adaptador_produccion.consultar_cuenta",
            return_value=CuentaPey(id=_ULID, codi_status="PROCESSING"),
        ):
            uno = self.client.post(_RUTA)
        self.assertEqual(uno.json()["paso"], 3)
        self.comercio.refresh_from_db()
        self.comercio.pey_codi_status_actualizado_en = timezone.now() - timedelta(
            seconds=60
        )
        self.comercio.save()
        with patch(
            "integracion.pey.adaptador_produccion.consultar_cuenta",
            return_value=CuentaPey(id=_ULID, codi_status="ACTIVE", clabe=_CLABE),
        ):
            dos = self.client.post(_RUTA)
        self.assertEqual(dos.json()["fase"], "activa")
