"""Cambiar la CLABE suelta la cuenta de pey. Un fallo de pey no responde 500."""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from ambito.cuenta_sync import sincronizar_codi_status
from ambito.models import Comercio, Membresia
from pey.cuentas import CuentaPey
from pey.tipos import ErrorPey

_CLABE = "012180015826225713"
_OTRA = "032180000118359719"
_ULID = "01J9ZQ4C8X7Y6W5V4T3S2R1Q0P"
_RUTA = "/api/cuenta/clabe/"


@override_settings(DEBUG=True, PEY_ADAPTADOR="produccion", PEY_API_KEY="llave")
class ClabeCambioYFalloPeyTests(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.comercio = Comercio.objects.create(
            nombre="Comercio A",
            clabe=_CLABE,
            pey_codi_status=Comercio.PeyCodiStatus.ACTIVE,
            pey_bank_account_id=_ULID,
        )
        usuario = User.objects.create_user(username="vendedor_a", password="pass")
        Membresia.objects.create(usuario=usuario, comercio=self.comercio)
        self.client.force_login(usuario)
        self.red = patch("urllib.request.urlopen", side_effect=AssertionError("red"))
        self.red.start()
        self.addCleanup(self.red.stop)

    def test_cambiar_clabe_deja_pending_sin_id(self) -> None:
        respuesta = self.client.post(_RUTA, {"clabe": _OTRA}, format="json")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json(), {"clabe": _OTRA})
        self.comercio.refresh_from_db()
        self.assertEqual(self.comercio.clabe, _OTRA)
        self.assertEqual(self.comercio.pey_codi_status, Comercio.PeyCodiStatus.PENDING)
        self.assertEqual(self.comercio.pey_bank_account_id, "")
        self.assertIsNotNone(self.comercio.pey_codi_status_actualizado_en)

    def test_misma_clabe_conserva_el_vinculo(self) -> None:
        with patch(
            "integracion.pey.adaptador_produccion.consultar_cuenta",
            return_value=CuentaPey(id=_ULID, codi_status="ACTIVE", clabe=_CLABE),
        ):
            respuesta = self.client.post(_RUTA, {"clabe": _CLABE}, format="json")
        self.assertEqual(respuesta.status_code, 200)
        self.comercio.refresh_from_db()
        self.assertEqual(self.comercio.clabe, _CLABE)
        self.assertEqual(self.comercio.pey_codi_status, Comercio.PeyCodiStatus.ACTIVE)
        self.assertEqual(self.comercio.pey_bank_account_id, _ULID)

    def test_vista_not_found_limpia_y_responde_200(self) -> None:
        with patch(
            "integracion.pey.adaptador_produccion.consultar_cuenta",
            side_effect=ErrorPey("BANK_ACCOUNT_NOT_FOUND", "no está", "req-404"),
        ):
            respuesta = self.client.post(_RUTA, {"clabe": _CLABE}, format="json")
        self.assertEqual(respuesta.status_code, 200)
        self.comercio.refresh_from_db()
        self.assertEqual(self.comercio.pey_codi_status, Comercio.PeyCodiStatus.PENDING)
        self.assertEqual(self.comercio.pey_bank_account_id, "")

    def test_vista_no_disponible_conserva_el_estado(self) -> None:
        with self.assertLogs("ambito.cuenta_sync", level="WARNING") as logs:
            with patch(
                "integracion.pey.adaptador_produccion.consultar_cuenta",
                side_effect=ErrorPey("NO_DISPONIBLE", "caído", "req-503"),
            ):
                respuesta = self.client.post(_RUTA, {"clabe": _CLABE}, format="json")
        self.assertEqual(respuesta.status_code, 200)
        self.comercio.refresh_from_db()
        self.assertEqual(self.comercio.pey_codi_status, Comercio.PeyCodiStatus.ACTIVE)
        self.assertEqual(self.comercio.pey_bank_account_id, _ULID)
        texto = " ".join(logs.output)
        self.assertIn("tipo=NO_DISPONIBLE", texto)
        self.assertIn("request_id=req-503", texto)

    def test_sincronizar_not_found_limpia_y_otro_error_conserva(self) -> None:
        with patch(
            "integracion.pey.adaptador_produccion.consultar_cuenta",
            side_effect=ErrorPey("BANK_ACCOUNT_NOT_FOUND", "no está", "req-404"),
        ):
            sincronizar_codi_status(self.comercio)
        self.comercio.refresh_from_db()
        self.assertEqual(self.comercio.pey_bank_account_id, "")
        self.assertEqual(self.comercio.pey_codi_status, Comercio.PeyCodiStatus.PENDING)

        self.comercio.pey_codi_status = Comercio.PeyCodiStatus.ACTIVE
        self.comercio.pey_bank_account_id = _ULID
        self.comercio.save()
        with self.assertLogs("ambito.cuenta_sync", level="WARNING"):
            with patch(
                "integracion.pey.adaptador_produccion.consultar_cuenta",
                side_effect=ErrorPey("NO_DISPONIBLE", "timeout", None),
            ):
                sincronizar_codi_status(self.comercio)
        self.comercio.refresh_from_db()
        self.assertEqual(self.comercio.pey_codi_status, Comercio.PeyCodiStatus.ACTIVE)
        self.assertEqual(self.comercio.pey_bank_account_id, _ULID)
