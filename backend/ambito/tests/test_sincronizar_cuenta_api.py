"""Sincronización por cuenta y ventana de 30 segundos."""

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from ambito.models import Comercio, Membresia
from ambito.operaciones_cuenta import ejecutar_pendientes, encolar_sync
from ambito.tests.soporte import crear_cuenta
from pey.cuentas import CuentaPey
from pey.tipos import ErrorPey


class SincronizarCuentaApiTests(TestCase):
    def setUp(self) -> None:
        self.comercio = Comercio.objects.create(nombre="Tienda")
        self.cuenta = crear_cuenta(self.comercio, estado="pending")
        usuario = User.objects.create_user(username="vend", password="pass")
        Membresia.objects.create(usuario=usuario, comercio=self.comercio, es_dueno=True)
        self.client = APIClient()
        self.client.force_login(usuario)
        self.ruta = f"/api/cuenta/cuentas/{self.cuenta.pk}/sincronizar/"

    def _sync(self, estado="ACTIVE", clabe=None):
        resultado = CuentaPey(
            self.cuenta.pey_bank_account_id,
            estado,
            clabe if clabe is not None else self.cuenta.clabe,
        )
        with patch(
            "ambito.operaciones_cuenta.consultar_cuenta", return_value=resultado
        ):
            return self.client.post(self.ruta, {}, format="json")

    def _adelantar(self):
        self.cuenta.operaciones.filter(tipo="sync").update(
            creado_en=timezone.now() - timedelta(seconds=31)
        )

    def test_processing_pey_queda_paso_3(self) -> None:
        respuesta = self._sync("PROCESSING")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["cuenta"]["codi_status"], "pending")
        self.assertFalse(respuesta.json()["cuenta"]["puede_cobrar"])

    def test_not_found_conserva_id(self) -> None:
        ident = self.cuenta.pey_bank_account_id
        with patch("ambito.operaciones_cuenta.consultar_cuenta",
                   side_effect=ErrorPey("BANK_ACCOUNT_NOT_FOUND", "no", "req-404")):
            respuesta = self.client.post(self.ruta, {}, format="json")
        self.assertEqual(respuesta.status_code, 200)
        self.cuenta.refresh_from_db()
        self.assertEqual(self.cuenta.pey_bank_account_id, ident)
        self.assertEqual(self.cuenta.codi_status, "pending")

    def test_rate_limit_429(self) -> None:
        self.assertEqual(self._sync().status_code, 200)
        respuesta = self._sync()
        self.assertEqual(respuesta.status_code, 429)
        self.assertGreater(respuesta.json()["reintento_en_segundos"], 0)

    def test_tras_ventana_sync_permitido(self) -> None:
        self._sync("PROCESSING")
        self._adelantar()
        respuesta = self._sync()
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.json()["cuenta"]["puede_cobrar"])

    def test_error_pey_conserva_estado_200(self) -> None:
        self.cuenta.codi_status = "active"
        self.cuenta.save(update_fields=["codi_status"])
        with patch("ambito.operaciones_cuenta.consultar_cuenta",
                   side_effect=ErrorPey("NO_DISPONIBLE", "caído", "req-503")):
            respuesta = self.client.post(self.ruta, {}, format="json")
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.json()["cuenta"]["puede_cobrar"])
        self.assertEqual(
            respuesta.json()["cuenta"]["ultimo_error"], "NO_DISPONIBLE req-503"
        )

    def test_webhook_active_luego_sync(self) -> None:
        encolar_sync(self.cuenta)
        self.cuenta.refresh_from_db()
        self.assertEqual(self.cuenta.codi_status, "pending")
        with patch("ambito.operaciones_cuenta.consultar_cuenta", return_value=CuentaPey(
            self.cuenta.pey_bank_account_id, "ACTIVE", self.cuenta.clabe
        )):
            ejecutar_pendientes()
        self.cuenta.refresh_from_db()
        self.assertEqual(self.cuenta.codi_status, "active")

    def test_misma_clabe_sync_restablece_active(self) -> None:
        respuesta = self._sync()
        self.assertEqual(respuesta.json()["cuenta"]["codi_status"], "active")

    def test_sin_sesion_403(self) -> None:
        self.client.logout()
        self.assertEqual(self.client.post(self.ruta).status_code, 403)

    def test_comercio_en_cuerpo_sincronizar_400(self) -> None:
        respuesta = self.client.post(self.ruta, {"comercio_id": 99}, format="json")
        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(self.cuenta.operaciones.exists())

    def test_dos_sync_separados_por_ventana(self) -> None:
        self.assertEqual(
            self._sync("PROCESSING").json()["cuenta"]["codi_status"], "pending"
        )
        self._adelantar()
        self.assertEqual(self._sync().json()["cuenta"]["codi_status"], "active")
        self.assertEqual(self.cuenta.operaciones.count(), 2)
