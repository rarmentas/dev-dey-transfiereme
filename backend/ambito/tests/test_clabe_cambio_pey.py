"""La ruta anterior no cambia CLABE; el sync conserva el destino."""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from ambito.models import Comercio, Membresia
from ambito.operaciones_cuenta import sincronizar
from ambito.tests.soporte import clabe_valida, crear_cuenta
from pey.tipos import ErrorPey


class ClabeCambioYFalloPeyTests(TestCase):
    def setUp(self) -> None:
        self.comercio = Comercio.objects.create(nombre="Comercio A")
        self.cuenta = crear_cuenta(self.comercio)
        self.identificador = self.cuenta.pey_bank_account_id
        usuario = User.objects.create_user(username="vendedor_a", password="pass")
        Membresia.objects.create(usuario=usuario, comercio=self.comercio, es_dueno=True)
        self.client = APIClient()
        self.client.force_login(usuario)

    def test_cambiar_clabe_no_modifica_la_cuenta(self) -> None:
        respuesta = self.client.post("/api/cuenta/clabe/", {"clabe": clabe_valida(2)},
                                     format="json")
        self.assertEqual(respuesta.json()["codigo"], "USAR_CUENTAS")
        self.cuenta.refresh_from_db()
        self.assertEqual(self.cuenta.clabe, clabe_valida(1))
        self.assertEqual(self.cuenta.pey_bank_account_id, self.identificador)

    def test_misma_clabe_conserva_el_vinculo(self) -> None:
        respuesta = self.client.post("/api/cuenta/clabe/", {"clabe": self.cuenta.clabe},
                                     format="json")
        self.assertEqual(respuesta.status_code, 409)
        self.cuenta.refresh_from_db()
        self.assertEqual(self.cuenta.pey_bank_account_id, self.identificador)
        self.assertEqual(self.cuenta.codi_status, "active")

    def test_vista_not_found_conserva_id_y_responde_200(self) -> None:
        with patch("ambito.operaciones_cuenta.consultar_cuenta",
                   side_effect=ErrorPey("BANK_ACCOUNT_NOT_FOUND", "no está")):
            respuesta = self.client.post(
                f"/api/cuenta/cuentas/{self.cuenta.pk}/sincronizar/", {}, format="json"
            )
        self.assertEqual(respuesta.status_code, 200)
        self.cuenta.refresh_from_db()
        self.assertEqual(self.cuenta.codi_status, "pending")
        self.assertEqual(self.cuenta.pey_bank_account_id, self.identificador)

    def test_vista_no_disponible_conserva_el_estado(self) -> None:
        with patch("ambito.operaciones_cuenta.consultar_cuenta",
                   side_effect=ErrorPey("NO_DISPONIBLE", "caído", "req-503")):
            respuesta = self.client.post(
                f"/api/cuenta/cuentas/{self.cuenta.pk}/sincronizar/", {}, format="json"
            )
        self.assertEqual(respuesta.status_code, 200)
        self.cuenta.refresh_from_db()
        self.assertEqual(self.cuenta.codi_status, "active")
        self.assertEqual(self.cuenta.ultimo_error, "NO_DISPONIBLE req-503")

    def test_sincronizar_not_found_y_otro_error_conservan_id(self) -> None:
        with patch("ambito.operaciones_cuenta.consultar_cuenta",
                   side_effect=ErrorPey("BANK_ACCOUNT_NOT_FOUND", "no está")):
            sincronizar(self.cuenta)
        self.cuenta.refresh_from_db()
        self.assertEqual(self.cuenta.pey_bank_account_id, self.identificador)
        self.assertEqual(self.cuenta.codi_status, "pending")
        self.cuenta.operaciones.all().delete()
        with patch("ambito.operaciones_cuenta.consultar_cuenta",
                   side_effect=ErrorPey("NO_DISPONIBLE", "timeout")):
            sincronizar(self.cuenta)
        self.cuenta.refresh_from_db()
        self.assertEqual(self.cuenta.pey_bank_account_id, self.identificador)
        self.assertEqual(self.cuenta.codi_status, "pending")
