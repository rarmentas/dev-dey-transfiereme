"""GET /api/ventas/<id>/. Sin red y sin consulta a pey."""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from ambito.models import Comercio, Membresia
from movimientos.models import Cobro, Movimiento
from sesion.middleware import _MENSAJE_SIN_SESION


class EstadoVentaApiTests(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.comercio_a = Comercio.objects.create(nombre="Comercio A")
        self.comercio_b = Comercio.objects.create(nombre="Comercio B")
        self.usuario_a = User.objects.create_user(username="vendedor_a", password="pass-a")
        self.usuario_b = User.objects.create_user(username="vendedor_b", password="pass-b")
        Membresia.objects.create(usuario=self.usuario_a, comercio=self.comercio_a)
        Membresia.objects.create(usuario=self.usuario_b, comercio=self.comercio_b)
        self._n = 0

    def _ident(self) -> str:
        self._n += 1
        return f"{self._n:04d}"

    def _movimiento(
        self,
        comercio: Comercio,
        *,
        canal: str = Movimiento.Canal.QR_VENTA,
        estado: str = Movimiento.Estado.PENDIENTE,
        vence_en=None,
        pagado_en=None,
        qr_string: str = "QR-VENTA",
        concepto: str = "Tacos",
        monto: str = "12.50",
    ) -> Movimiento:
        ident = self._ident()
        es_notificacion = canal == Movimiento.Canal.NOTIFICACION
        cobro = Cobro.objects.create(
            comercio=comercio,
            canal=canal,
            monto=Decimal("0") if canal == Movimiento.Canal.QR_GENERAL else Decimal(monto),
            concepto=concepto,
            vence_en=vence_en,
            pey_qr_id=None if es_notificacion else f"qr-{ident}",
            pey_transaction_id=f"tx-{ident}" if es_notificacion else None,
            qr_string="" if es_notificacion else qr_string,
        )
        return Movimiento.objects.create(
            comercio=comercio,
            cobro=cobro,
            monto=Decimal(monto),
            concepto=concepto,
            concepto_visible=concepto,
            canal=canal,
            estado=estado,
            origen=Movimiento.Origen.ORIGEN_DESARROLLO,
            pagado_en=pagado_en,
        )

    def _entrar(self, usuario: User) -> None:
        self.client.force_login(usuario)

    def test_pendiente_vigente_sigue_pendiente(self) -> None:
        movimiento = self._movimiento(
            self.comercio_a,
            vence_en=timezone.now() + timedelta(minutes=5),
        )
        self._entrar(self.usuario_a)
        respuesta = self.client.get(f"/api/ventas/{movimiento.pk}/")
        self.assertEqual(respuesta.status_code, 200)
        cuerpo = respuesta.json()
        self.assertEqual(cuerpo["estado"], Movimiento.Estado.PENDIENTE)
        self.assertEqual(cuerpo["movimiento_id"], movimiento.pk)
        self.assertEqual(cuerpo["canal"], Movimiento.Canal.QR_VENTA)
        self.assertEqual(cuerpo["monto"], "12.50")
        self.assertEqual(cuerpo["concepto"], "Tacos")
        self.assertEqual(cuerpo["qr_string"], "QR-VENTA")
        self.assertIsNone(cuerpo["pagado_en"])
        movimiento.refresh_from_db()
        self.assertEqual(movimiento.estado, Movimiento.Estado.PENDIENTE)

    def test_plazo_cumplido_queda_vencido_y_persistido(self) -> None:
        movimiento = self._movimiento(
            self.comercio_a,
            vence_en=timezone.now() - timedelta(seconds=1),
        )
        self._entrar(self.usuario_a)
        respuesta = self.client.get(f"/api/ventas/{movimiento.pk}/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["estado"], Movimiento.Estado.VENCIDO)
        movimiento.refresh_from_db()
        self.assertEqual(movimiento.estado, Movimiento.Estado.VENCIDO)
        self.assertIsNone(movimiento.pagado_en)

    def test_vence_en_nulo_no_vence(self) -> None:
        movimiento = self._movimiento(self.comercio_a, vence_en=None)
        self._entrar(self.usuario_a)
        respuesta = self.client.get(f"/api/ventas/{movimiento.pk}/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["estado"], Movimiento.Estado.PENDIENTE)
        self.assertIsNone(respuesta.json()["vence_en"])
        movimiento.refresh_from_db()
        self.assertEqual(movimiento.estado, Movimiento.Estado.PENDIENTE)

    def test_pagado_devuelve_pagado_en(self) -> None:
        pagado_en = timezone.now() - timedelta(minutes=2)
        movimiento = self._movimiento(
            self.comercio_a,
            estado=Movimiento.Estado.PAGADO,
            vence_en=timezone.now() + timedelta(minutes=5),
            pagado_en=pagado_en,
        )
        self._entrar(self.usuario_a)
        respuesta = self.client.get(f"/api/ventas/{movimiento.pk}/")
        self.assertEqual(respuesta.status_code, 200)
        cuerpo = respuesta.json()
        self.assertEqual(cuerpo["estado"], Movimiento.Estado.PAGADO)
        self.assertEqual(cuerpo["pagado_en"], movimiento.pagado_en.isoformat())
        movimiento.refresh_from_db()
        self.assertEqual(movimiento.estado, Movimiento.Estado.PAGADO)

    def test_otro_comercio_responde_404(self) -> None:
        movimiento = self._movimiento(
            self.comercio_b,
            vence_en=timezone.now() + timedelta(minutes=5),
        )
        self._entrar(self.usuario_a)
        respuesta = self.client.get(f"/api/ventas/{movimiento.pk}/")
        self.assertEqual(respuesta.status_code, 404)
        self.assertEqual(respuesta.json()["detail"], "No encontrado.")

    def test_qr_general_responde_404(self) -> None:
        movimiento = self._movimiento(
            self.comercio_a,
            canal=Movimiento.Canal.QR_GENERAL,
            monto="10.00",
        )
        self._entrar(self.usuario_a)
        respuesta = self.client.get(f"/api/ventas/{movimiento.pk}/")
        self.assertEqual(respuesta.status_code, 404)
        movimiento.refresh_from_db()
        self.assertEqual(movimiento.estado, Movimiento.Estado.PENDIENTE)

    def test_sin_sesion_responde_403(self) -> None:
        movimiento = self._movimiento(
            self.comercio_a,
            vence_en=timezone.now() + timedelta(minutes=5),
        )
        respuesta = self.client.get(f"/api/ventas/{movimiento.pk}/")
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(respuesta.json()["detail"], _MENSAJE_SIN_SESION)

    def test_comercio_en_query_responde_400(self) -> None:
        movimiento = self._movimiento(
            self.comercio_a,
            vence_en=timezone.now() + timedelta(minutes=5),
        )
        self._entrar(self.usuario_a)
        respuesta = self.client.get(
            f"/api/ventas/{movimiento.pk}/?comercio={self.comercio_b.pk}",
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("comercio", respuesta.json()["detail"])

    def test_notificacion_devuelve_qr_string_vacio(self) -> None:
        movimiento = self._movimiento(
            self.comercio_a,
            canal=Movimiento.Canal.NOTIFICACION,
            vence_en=timezone.now() + timedelta(minutes=5),
        )
        self._entrar(self.usuario_a)
        respuesta = self.client.get(f"/api/ventas/{movimiento.pk}/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["qr_string"], "")
        self.assertEqual(respuesta.json()["canal"], Movimiento.Canal.NOTIFICACION)
