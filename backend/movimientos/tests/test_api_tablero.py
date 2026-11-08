from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from ambito.models import Comercio, Membresia
from movimientos.models import Movimiento
from sesion.middleware import _MENSAJE_SIN_SESION

UTC = ZoneInfo("UTC")
MEXICO = ZoneInfo("America/Mexico_City")
# 23:30 del 7-nov-2026 en México (05:30 UTC del 8) y 00:30 del 8 (06:30 UTC).
NOCHE_7 = datetime(2026, 11, 8, 5, 30, tzinfo=UTC)
MADRUGADA_8 = datetime(2026, 11, 8, 6, 30, tzinfo=UTC)
MEDIODIA_6 = datetime(2026, 11, 6, 18, 0, tzinfo=UTC)


class TableroApiTests(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.comercio_a = Comercio.objects.create(nombre="Comercio A")
        self.comercio_b = Comercio.objects.create(nombre="Comercio B")
        self.usuario_a = User.objects.create_user(username="vendedor_a", password="pass-a")
        self.usuario_b = User.objects.create_user(username="vendedor_b", password="pass-b")
        Membresia.objects.create(usuario=self.usuario_a, comercio=self.comercio_a)
        Membresia.objects.create(usuario=self.usuario_b, comercio=self.comercio_b)

    def _crear(self, comercio: Comercio, **kwargs) -> Movimiento:
        datos = {
            "comercio": comercio,
            "monto": Decimal("10.00"),
            "concepto": "Transferencia",
            "canal": Movimiento.Canal.QR_GENERAL,
            "origen": Movimiento.Origen.ORIGEN_PEY,
            "estado": Movimiento.Estado.PAGADO,
            "pagado_en": datetime(2026, 11, 7, 18, 0, tzinfo=UTC),
        }
        datos.update(kwargs)
        return Movimiento.objects.create(**datos)

    def _entrar(self) -> None:
        self.client.force_login(self.usuario_a)

    def test_origen_desarrollo_solo_en_desarrollo(self) -> None:
        self._crear(self.comercio_a, monto=Decimal("10.00"))
        self._crear(
            self.comercio_a,
            origen=Movimiento.Origen.ORIGEN_DESARROLLO,
            monto=Decimal("0.01"),
            concepto="Prueba",
        )
        self._entrar()
        respuesta = self.client.get("/api/movimientos/tablero/")
        self.assertEqual(respuesta.status_code, 200)
        cuerpo = respuesta.json()
        self.assertEqual(cuerpo["zona"], "America/Mexico_City")
        self.assertEqual(cuerpo["confirmado"]["total"], "10.00")
        self.assertEqual(cuerpo["desarrollo"]["total"], "0.01")
        self.assertEqual(cuerpo["confirmado"]["filas"][0]["total"], "10.00")
        self.assertEqual(cuerpo["desarrollo"]["filas"][0]["concepto"], "prueba")
        self.assertNotIn("0.01", [fila["total"] for fila in cuerpo["confirmado"]["filas"]])

    def test_otro_comercio_no_aparece(self) -> None:
        self._crear(self.comercio_a, monto=Decimal("1.00"))
        self._crear(self.comercio_b, monto=Decimal("99.00"), concepto="Ajeno")
        self._entrar()
        cuerpo = self.client.get("/api/movimientos/tablero/").json()
        self.assertEqual(cuerpo["confirmado"]["total"], "1.00")
        self.assertEqual(cuerpo["desarrollo"]["total"], "0.00")
        conceptos = [fila["concepto"] for fila in cuerpo["confirmado"]["filas"]]
        self.assertNotIn("ajeno", conceptos)

    def test_sin_sesion_devuelve_403(self) -> None:
        respuesta = self.client.get("/api/movimientos/tablero/")
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(respuesta.json()["detail"], _MENSAJE_SIN_SESION)

    def test_comercio_en_query_devuelve_400(self) -> None:
        self._entrar()
        for query in (
            f"comercio_id={self.comercio_b.pk}",
            f"comercio={self.comercio_b.pk}",
        ):
            with self.subTest(query=query):
                respuesta = self.client.get(f"/api/movimientos/tablero/?{query}")
                self.assertEqual(respuesta.status_code, 400)
                self.assertIn("comercio", respuesta.json()["detail"])

    def test_desde_hasta_son_dias_locales_inclusivos(self) -> None:
        self._crear(self.comercio_a, pagado_en=MEDIODIA_6, monto=Decimal("1.00"), concepto="Seis")
        self._crear(self.comercio_a, pagado_en=NOCHE_7, monto=Decimal("2.00"), concepto="Noche")
        self._crear(
            self.comercio_a,
            pagado_en=MADRUGADA_8,
            monto=Decimal("4.00"),
            concepto="Madrugada",
        )
        self._entrar()

        solo_7 = self.client.get(
            "/api/movimientos/tablero/?desde=2026-11-07&hasta=2026-11-07"
        )
        self.assertEqual(solo_7.status_code, 200)
        self.assertEqual(solo_7.json()["confirmado"]["total"], "2.00")
        self.assertEqual(solo_7.json()["confirmado"]["filas"][0]["dia"], "2026-11-07")

        desde_8 = self.client.get("/api/movimientos/tablero/?desde=2026-11-08")
        self.assertEqual(desde_8.json()["confirmado"]["total"], "4.00")
        self.assertEqual(desde_8.json()["confirmado"]["filas"][0]["dia"], "2026-11-08")

        hasta_7 = self.client.get("/api/movimientos/tablero/?hasta=2026-11-07")
        self.assertEqual(hasta_7.json()["confirmado"]["total"], "3.00")

    def test_hasta_incluye_el_ultimo_segundo_local_y_excluye_la_medianoche(self) -> None:
        self._crear(
            self.comercio_a,
            pagado_en=datetime(2026, 11, 7, 23, 59, 59, tzinfo=MEXICO),
            monto=Decimal("1.00"),
            concepto="Cierre",
        )
        self._crear(
            self.comercio_a,
            pagado_en=datetime(2026, 11, 8, 0, 0, tzinfo=MEXICO),
            monto=Decimal("9.00"),
            concepto="Siguiente",
        )
        self._entrar()
        respuesta = self.client.get("/api/movimientos/tablero/?hasta=2026-11-07")
        self.assertEqual(respuesta.status_code, 200)
        cuerpo = respuesta.json()
        self.assertEqual(cuerpo["confirmado"]["total"], "1.00")
        self.assertEqual(len(cuerpo["confirmado"]["filas"]), 1)
        self.assertEqual(cuerpo["confirmado"]["filas"][0]["dia"], "2026-11-07")
        self.assertEqual(cuerpo["confirmado"]["filas"][0]["cantidad"], 1)

    def test_fecha_invalida_devuelve_400(self) -> None:
        self._entrar()
        for query in ("desde=ayer", "hasta=07-11-2026", "desde=2026-02-31", "hasta=2026-11-7"):
            with self.subTest(query=query):
                respuesta = self.client.get(f"/api/movimientos/tablero/?{query}")
                self.assertEqual(respuesta.status_code, 400)
                self.assertIn("YYYY-MM-DD", respuesta.json()["detail"])

    def test_montos_son_cadenas_con_dos_decimales(self) -> None:
        self._crear(self.comercio_a, monto=Decimal("0.01"))
        self._entrar()
        cuerpo = self.client.get("/api/movimientos/tablero/").json()
        self.assertEqual(cuerpo["confirmado"]["total"], "0.01")
        self.assertIsInstance(cuerpo["confirmado"]["total"], str)
        self.assertEqual(cuerpo["desarrollo"]["total"], "0.00")
        self.assertIsInstance(cuerpo["desarrollo"]["total"], str)
        fila = cuerpo["confirmado"]["filas"][0]
        self.assertEqual(fila["total"], "0.01")
        self.assertIsInstance(fila["total"], str)
        self.assertEqual(
            set(fila),
            {"dia", "canal", "concepto", "etiqueta", "total", "cantidad"},
        )
        self.assertIsInstance(fila["cantidad"], int)

    def test_lectura_incluye_pagado_en(self) -> None:
        pendiente = self._crear(
            self.comercio_a,
            estado=Movimiento.Estado.PENDIENTE,
            pagado_en=None,
            concepto="Pendiente",
        )
        pagado = self._crear(self.comercio_a, monto=Decimal("0.01"))
        self._entrar()

        cuerpo_pendiente = self.client.get(f"/api/movimientos/{pendiente.pk}/").json()
        self.assertIn("pagado_en", cuerpo_pendiente)
        self.assertIsNone(cuerpo_pendiente["pagado_en"])

        cuerpo_pagado = self.client.get(f"/api/movimientos/{pagado.pk}/").json()
        self.assertIsInstance(cuerpo_pagado["pagado_en"], str)
        self.assertIn("2026-11-07", cuerpo_pagado["pagado_en"])
