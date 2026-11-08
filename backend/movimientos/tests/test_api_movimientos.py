from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from ambito.models import Comercio, Membresia
from movimientos.models import Cobro, Movimiento
from sesion.middleware import _MENSAJE_SIN_SESION


class MovimientosApiTests(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()

        self.comercio_a = Comercio.objects.create(nombre="Comercio A")
        self.comercio_b = Comercio.objects.create(nombre="Comercio B")

        self.usuario_a = User.objects.create_user(username="vendedor_a", password="pass-a")
        self.usuario_b = User.objects.create_user(username="vendedor_b", password="pass-b")

        Membresia.objects.create(usuario=self.usuario_a, comercio=self.comercio_a)
        Membresia.objects.create(usuario=self.usuario_b, comercio=self.comercio_b)

        self.movimiento_a = self._crear_movimiento(self.comercio_a, concepto="Cobro A")
        self.movimiento_b = self._crear_movimiento(self.comercio_b, concepto="Cobro B")

    def _crear_movimiento(self, comercio: Comercio, **kwargs) -> Movimiento:
        datos = {
            "comercio": comercio,
            "monto": Decimal("10.00"),
            "concepto": "Transferencia",
            "canal": Movimiento.Canal.QR_VENTA,
            "origen": Movimiento.Origen.ORIGEN_DESARROLLO,
        }
        datos.update(kwargs)
        return Movimiento.objects.create(**datos)

    def _entrar(self, usuario: User, password: str) -> None:
        self.client.force_login(usuario)

    def test_listado_sesion_a_no_incluye_movimiento_de_b(self) -> None:
        self._entrar(self.usuario_a, "pass-a")
        respuesta = self.client.get("/api/movimientos/")
        self.assertEqual(respuesta.status_code, 200)
        ids = [item["id"] for item in respuesta.json()]
        self.assertIn(self.movimiento_a.pk, ids)
        self.assertNotIn(self.movimiento_b.pk, ids)

    def test_listado_sesion_b_no_incluye_movimiento_de_a(self) -> None:
        self._entrar(self.usuario_b, "pass-b")
        respuesta = self.client.get("/api/movimientos/")
        self.assertEqual(respuesta.status_code, 200)
        ids = [item["id"] for item in respuesta.json()]
        self.assertIn(self.movimiento_b.pk, ids)
        self.assertNotIn(self.movimiento_a.pk, ids)

    def test_listado_sin_sesion_devuelve_403_middleware(self) -> None:
        respuesta = self.client.get("/api/movimientos/")
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(respuesta.json()["detail"], _MENSAJE_SIN_SESION)

    def test_detalle_ajeno_responde_404(self) -> None:
        self._entrar(self.usuario_a, "pass-a")
        respuesta = self.client.get(f"/api/movimientos/{self.movimiento_b.pk}/")
        self.assertEqual(respuesta.status_code, 404)
        self.assertEqual(respuesta.json()["detail"], "No encontrado.")

    def test_detalle_propio_responde_200(self) -> None:
        self._entrar(self.usuario_a, "pass-a")
        respuesta = self.client.get(f"/api/movimientos/{self.movimiento_a.pk}/")
        self.assertEqual(respuesta.status_code, 200)
        cuerpo = respuesta.json()
        self.assertEqual(cuerpo["id"], self.movimiento_a.pk)
        self.assertEqual(cuerpo["concepto_visible"], "Cobro A")
        self.assertEqual(cuerpo["canal"], Movimiento.Canal.QR_VENTA)
        self.assertEqual(cuerpo["estado"], Movimiento.Estado.PENDIENTE)
        self.assertEqual(cuerpo["origen"], Movimiento.Origen.ORIGEN_DESARROLLO)
        self.assertEqual(cuerpo["monto"], "10.00")
        self.assertIn("creado_en", cuerpo)

    def test_query_comercio_id_prohibida(self) -> None:
        self._entrar(self.usuario_a, "pass-a")
        respuesta = self.client.get(
            f"/api/movimientos/?comercio_id={self.comercio_b.pk}",
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("comercio_id", respuesta.json()["detail"])

    def test_query_comercio_prohibida(self) -> None:
        self._entrar(self.usuario_a, "pass-a")
        respuesta = self.client.get(f"/api/movimientos/?comercio={self.comercio_b.pk}")
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("comercio", respuesta.json()["detail"])

    def test_monto_se_serializa_como_cadena(self) -> None:
        self._entrar(self.usuario_a, "pass-a")
        movimiento = self._crear_movimiento(
            self.comercio_a,
            monto=Decimal("0.01"),
            concepto="Un centavo",
        )
        respuesta = self.client.get(f"/api/movimientos/{movimiento.pk}/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["monto"], "0.01")
        self.assertIsInstance(respuesta.json()["monto"], str)

    def test_listado_incluye_movimiento_con_cobro_en_otro_comercio_aislado(self) -> None:
        cobro_b = Cobro.objects.create(
            comercio=self.comercio_b,
            canal=Movimiento.Canal.QR_VENTA,
            monto=Decimal("25.00"),
            concepto="Venta B",
            pey_qr_id="QR-B-1",
        )
        movimiento_cobro_b = Movimiento.objects.create(
            comercio=cobro_b.comercio,
            cobro=cobro_b,
            monto=Decimal("25.00"),
            concepto=cobro_b.concepto,
            canal=cobro_b.canal,
            origen=Movimiento.Origen.ORIGEN_DESARROLLO,
        )
        self._entrar(self.usuario_a, "pass-a")
        respuesta = self.client.get("/api/movimientos/")
        self.assertEqual(respuesta.status_code, 200)
        ids = [item["id"] for item in respuesta.json()]
        self.assertNotIn(movimiento_cobro_b.pk, ids)

    def test_listado_devuelve_los_tres_canales_con_concepto_visible(self) -> None:
        general = self._crear_movimiento(
            self.comercio_a,
            monto=Decimal("1.00"),
            concepto="QR del mostrador",
            concepto_visible="QR del mostrador",
            canal=Movimiento.Canal.QR_GENERAL,
            estado=Movimiento.Estado.PAGADO,
            origen=Movimiento.Origen.ORIGEN_PEY,
        )
        venta = self._crear_movimiento(
            self.comercio_a,
            monto=Decimal("2.50"),
            concepto="Venta de contado",
            concepto_visible="Venta de contado",
            canal=Movimiento.Canal.QR_VENTA,
            estado=Movimiento.Estado.PENDIENTE,
            origen=Movimiento.Origen.ORIGEN_DESARROLLO,
        )
        aviso = self._crear_movimiento(
            self.comercio_a,
            monto=Decimal("3.00"),
            concepto="Aviso al cliente",
            concepto_visible="Aviso al cliente",
            canal=Movimiento.Canal.NOTIFICACION,
            estado=Movimiento.Estado.VENCIDO,
            origen=Movimiento.Origen.ORIGEN_PEY,
        )

        self._entrar(self.usuario_a, "pass-a")
        respuesta = self.client.get("/api/movimientos/")
        self.assertEqual(respuesta.status_code, 200)

        por_id = {item["id"]: item for item in respuesta.json()}
        esperados = (
            (general, Movimiento.Canal.QR_GENERAL, Movimiento.Estado.PAGADO),
            (venta, Movimiento.Canal.QR_VENTA, Movimiento.Estado.PENDIENTE),
            (aviso, Movimiento.Canal.NOTIFICACION, Movimiento.Estado.VENCIDO),
        )
        for movimiento, canal, estado in esperados:
            self.assertIn(movimiento.pk, por_id)
            item = por_id[movimiento.pk]
            self.assertEqual(item["canal"], canal)
            self.assertEqual(item["concepto_visible"], movimiento.concepto_visible)
            self.assertEqual(item["estado"], estado)
