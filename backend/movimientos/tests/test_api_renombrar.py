from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from ambito.models import Comercio, Membresia
from movimientos.models import Cobro, Movimiento
from sesion.middleware import _MENSAJE_SIN_SESION

_MENSAJE_SOLO_PAGADO = "Solo se puede renombrar un movimiento cobrado."


def _puerto_prohibido(*args, **kwargs):
    raise AssertionError("no debe llamar al puerto")


class RenombrarConceptoApiTests(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.comercio_a = Comercio.objects.create(nombre="Comercio A")
        self.comercio_b = Comercio.objects.create(nombre="Comercio B")
        self.usuario_a = User.objects.create_user(username="vendedor_a", password="pass-a")
        self.usuario_b = User.objects.create_user(username="vendedor_b", password="pass-b")
        Membresia.objects.create(usuario=self.usuario_a, comercio=self.comercio_a)
        Membresia.objects.create(usuario=self.usuario_b, comercio=self.comercio_b)
        self.cobro = Cobro.objects.create(
            comercio=self.comercio_a,
            canal=Movimiento.Canal.QR_VENTA,
            monto=Decimal("25.00"),
            concepto="Transferencia",
            pey_qr_id="qr-renombrar-1",
            qr_string="cody-dev://qr/qr-renombrar-1",
        )
        self.pagado = self._crear(
            estado=Movimiento.Estado.PAGADO,
            cobro=self.cobro,
        )
        self.pendiente = self._crear(estado=Movimiento.Estado.PENDIENTE)
        self.vencido = self._crear(estado=Movimiento.Estado.VENCIDO)

    def _crear(self, **kwargs) -> Movimiento:
        datos = {
            "comercio": self.comercio_a,
            "monto": Decimal("25.00"),
            "concepto": "Transferencia",
            "canal": Movimiento.Canal.QR_VENTA,
            "origen": Movimiento.Origen.ORIGEN_DESARROLLO,
            "estado": Movimiento.Estado.PENDIENTE,
        }
        datos.update(kwargs)
        return Movimiento.objects.create(**datos)

    def _entrar(self, usuario: User | None = None) -> None:
        self.client.force_login(usuario or self.usuario_a)

    def _patch(self, pk: int, cuerpo, query: str = ""):
        with patch("pey.seleccion.obtener_puerto", side_effect=_puerto_prohibido):
            return self.client.patch(
                f"/api/movimientos/{pk}/{query}",
                cuerpo,
                format="json",
            )

    def test_pagado_renombra_el_visible_y_el_tablero_agrupa_tortas(self) -> None:
        self._entrar()
        respuesta = self._patch(self.pagado.pk, {"concepto_visible": "  Tortas  "})
        self.assertEqual(respuesta.status_code, 200)
        cuerpo = respuesta.json()
        self.assertEqual(cuerpo["concepto_visible"], "Tortas")
        self.assertEqual(cuerpo["concepto"], "Transferencia")
        self.assertEqual(cuerpo["estado"], Movimiento.Estado.PAGADO)

        self.pagado.refresh_from_db()
        self.cobro.refresh_from_db()
        self.assertEqual(self.pagado.concepto_visible, "Tortas")
        self.assertEqual(self.pagado.concepto, "Transferencia")
        self.assertEqual(self.cobro.concepto, "Transferencia")

        tablero = self.client.get("/api/movimientos/tablero/")
        self.assertEqual(tablero.status_code, 200)
        filas = tablero.json()["desarrollo"]["filas"]
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0]["concepto"], "tortas")
        self.assertEqual(filas[0]["etiqueta"], "Tortas")
        self.assertEqual(tablero.json()["confirmado"]["filas"], [])

    def test_pendiente_y_vencido_responden_409_sin_cambios(self) -> None:
        self._entrar()
        for movimiento in (self.pendiente, self.vencido):
            with self.subTest(estado=movimiento.estado):
                antes = movimiento.concepto_visible
                respuesta = self._patch(
                    movimiento.pk,
                    {"concepto_visible": "Tortas"},
                )
                self.assertEqual(respuesta.status_code, 409)
                self.assertEqual(respuesta.json(), {"detail": _MENSAJE_SOLO_PAGADO})
                movimiento.refresh_from_db()
                self.assertEqual(movimiento.concepto_visible, antes)
                self.assertEqual(movimiento.concepto, "Transferencia")

    def test_ambito_cuerpo_y_texto_invalidos(self) -> None:
        ajeno = self.client.patch(
            f"/api/movimientos/{self.pagado.pk}/",
            {"concepto_visible": "Tortas"},
            format="json",
        )
        self.assertEqual(ajeno.status_code, 403)
        self.assertEqual(ajeno.json()["detail"], _MENSAJE_SIN_SESION)

        self._entrar(self.usuario_b)
        otro = self._patch(self.pagado.pk, {"concepto_visible": "Tortas"})
        self.assertEqual(otro.status_code, 404)
        self.assertEqual(otro.json()["detail"], "No encontrado.")

        self._entrar(self.usuario_a)
        comercio = self._patch(
            self.pagado.pk,
            {"concepto_visible": "Tortas", "comercio": self.comercio_b.pk},
        )
        self.assertEqual(comercio.status_code, 400)
        self.assertIn("comercio", comercio.json()["detail"].lower())

        query = self._patch(
            self.pagado.pk,
            {"concepto_visible": "Tortas"},
            query="?comercio=2",
        )
        self.assertEqual(query.status_code, 400)
        self.assertIn("comercio", query.json()["detail"].lower())

        for cuerpo in (
            {"concepto_visible": "Tortas", "concepto": "Otro"},
            {"concepto_visible": "Tortas", "monto": "1.00"},
            {"concepto_visible": "Tortas", "estado": "pendiente"},
            {"concepto": "Tortas"},
            {"concepto_visible": ""},
            {"concepto_visible": "   "},
            {"concepto_visible": "a" * 501},
        ):
            with self.subTest(cuerpo=cuerpo):
                respuesta = self._patch(self.pagado.pk, cuerpo)
                self.assertEqual(respuesta.status_code, 400)

        self.pagado.refresh_from_db()
        self.cobro.refresh_from_db()
        self.assertEqual(self.pagado.concepto_visible, "Transferencia")
        self.assertEqual(self.pagado.concepto, "Transferencia")
        self.assertEqual(self.cobro.concepto, "Transferencia")
