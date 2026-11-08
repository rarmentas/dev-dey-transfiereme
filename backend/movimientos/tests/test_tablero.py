from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from ambito.models import Comercio
from movimientos.models import Movimiento
from movimientos.tablero import agrupar, normalizar_concepto, partir_por_origen

UTC = ZoneInfo("UTC")
# 23:30 del 7 de noviembre de 2026 en México es 05:30 UTC del 8.
NOCHE_7 = datetime(2026, 11, 8, 5, 30, tzinfo=UTC)
# 00:30 del 8 de noviembre de 2026 en México es 06:30 UTC del 8.
MADRUGADA_8 = datetime(2026, 11, 8, 6, 30, tzinfo=UTC)


class TableroDominioTests(TestCase):
    def setUp(self) -> None:
        self.comercio = Comercio.objects.create(nombre="Abarrotes Centro")

    def _crear(self, **kwargs) -> Movimiento:
        datos = {
            "comercio": self.comercio,
            "monto": Decimal("10.00"),
            "concepto": "Transferencia",
            "canal": Movimiento.Canal.QR_GENERAL,
            "origen": Movimiento.Origen.ORIGEN_PEY,
        }
        datos.update(kwargs)
        return Movimiento.objects.create(**datos)

    def test_normalizar_concepto_colapsa_y_vacio_cae_en_transferencia(self) -> None:
        self.assertEqual(
            normalizar_concepto("  Tortas   de  Pollo "),
            "tortas de pollo",
        )
        self.assertEqual(normalizar_concepto(""), "transferencia")
        self.assertEqual(normalizar_concepto("   "), "transferencia")
        self.assertEqual(normalizar_concepto(None), "transferencia")

    def test_variantes_de_transferencia_suman_una_fila(self) -> None:
        self._crear(
            concepto="Transferencia",
            monto=Decimal("10.00"),
            pagado_en=datetime(2026, 11, 7, 16, 0, tzinfo=UTC),
            estado=Movimiento.Estado.PAGADO,
        )
        self._crear(
            concepto="transferencia ",
            monto=Decimal("0.50"),
            pagado_en=datetime(2026, 11, 7, 17, 0, tzinfo=UTC),
            estado=Movimiento.Estado.PAGADO,
        )
        reciente = self._crear(
            concepto="  TRANSFERENCIA",
            monto=Decimal("0.01"),
            pagado_en=datetime(2026, 11, 7, 18, 0, tzinfo=UTC),
            estado=Movimiento.Estado.PAGADO,
        )

        filas = agrupar(Movimiento.objects.all())
        self.assertEqual(len(filas), 1)
        fila = filas[0]
        self.assertEqual(fila.concepto, "transferencia")
        self.assertEqual(fila.total, Decimal("10.51"))
        self.assertIsInstance(fila.total, Decimal)
        self.assertEqual(fila.cantidad, 3)
        self.assertEqual(fila.etiqueta, reciente.concepto_visible)
        self.assertEqual(fila.dia.isoformat(), "2026-11-07")
        self.assertEqual(fila.canal, Movimiento.Canal.QR_GENERAL)

    def test_mismo_concepto_y_dia_en_canales_distintos_son_dos_filas(self) -> None:
        instante = datetime(2026, 11, 7, 18, 0, tzinfo=UTC)
        self._crear(
            canal=Movimiento.Canal.QR_VENTA,
            estado=Movimiento.Estado.PAGADO,
            pagado_en=instante,
            monto=Decimal("2.00"),
        )
        self._crear(
            canal=Movimiento.Canal.QR_GENERAL,
            estado=Movimiento.Estado.PAGADO,
            pagado_en=instante,
            monto=Decimal("3.00"),
        )

        filas = agrupar(Movimiento.objects.all())
        self.assertEqual(
            [(fila.canal, fila.total) for fila in filas],
            [
                (Movimiento.Canal.QR_GENERAL, Decimal("3.00")),
                (Movimiento.Canal.QR_VENTA, Decimal("2.00")),
            ],
        )
        self.assertEqual({fila.concepto for fila in filas}, {"transferencia"})
        self.assertEqual({fila.dia.isoformat() for fila in filas}, {"2026-11-07"})

    def test_dia_local_de_mexico_aunque_utc_ya_cambio_de_fecha(self) -> None:
        self._crear(
            estado=Movimiento.Estado.PAGADO,
            pagado_en=NOCHE_7,
            monto=Decimal("1.00"),
            concepto="Noche",
        )
        self._crear(
            estado=Movimiento.Estado.PAGADO,
            pagado_en=MADRUGADA_8,
            monto=Decimal("4.00"),
            concepto="Madrugada",
        )

        filas = agrupar(Movimiento.objects.all())
        self.assertEqual(
            [(fila.dia.isoformat(), fila.total) for fila in filas],
            [
                ("2026-11-08", Decimal("4.00")),
                ("2026-11-07", Decimal("1.00")),
            ],
        )

    def test_origen_desarrollo_no_entra_en_el_total_confirmado(self) -> None:
        instante = datetime(2026, 11, 7, 18, 0, tzinfo=UTC)
        pey = self._crear(
            origen=Movimiento.Origen.ORIGEN_PEY,
            estado=Movimiento.Estado.PAGADO,
            pagado_en=instante,
            monto=Decimal("10.00"),
        )
        desarrollo = self._crear(
            origen=Movimiento.Origen.ORIGEN_DESARROLLO,
            estado=Movimiento.Estado.PAGADO,
            pagado_en=instante,
            monto=Decimal("0.01"),
        )

        confirmado, de_desarrollo = partir_por_origen([pey, desarrollo])
        filas_confirmado = agrupar(confirmado)
        filas_desarrollo = agrupar(de_desarrollo)
        self.assertEqual(filas_confirmado[0].total, Decimal("10.00"))
        self.assertEqual(filas_desarrollo[0].total, Decimal("0.01"))
        self.assertEqual(
            sum((fila.total for fila in filas_confirmado), Decimal("0")),
            Decimal("10.00"),
        )
        self.assertNotEqual(filas_confirmado[0].total, Decimal("10.01"))

    def test_pendientes_y_vencidos_no_cuentan(self) -> None:
        self._crear(estado=Movimiento.Estado.PENDIENTE, monto=Decimal("8.00"))
        vencido = self._crear(monto=Decimal("9.00"))
        vencido.cambiar_estado(Movimiento.Estado.VENCIDO)
        self._crear(
            estado=Movimiento.Estado.PAGADO,
            pagado_en=datetime(2026, 11, 7, 18, 0, tzinfo=UTC),
            monto=Decimal("1.50"),
        )

        filas = agrupar(Movimiento.objects.all())
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0].total, Decimal("1.50"))
        self.assertEqual(filas[0].cantidad, 1)

    def test_cambiar_estado_pagado_fija_pagado_en_y_vencido_no(self) -> None:
        antes = timezone.now()
        pagado = self._crear()
        self.assertIsNone(pagado.pagado_en)
        pagado.cambiar_estado(Movimiento.Estado.PAGADO)
        leido = Movimiento.objects.get(pk=pagado.pk)
        self.assertEqual(leido.estado, Movimiento.Estado.PAGADO)
        self.assertIsNotNone(leido.pagado_en)
        self.assertGreaterEqual(leido.pagado_en, antes)
        self.assertEqual(pagado.pagado_en, leido.pagado_en)

        vencido = self._crear()
        vencido.cambiar_estado(Movimiento.Estado.VENCIDO)
        self.assertIsNone(Movimiento.objects.get(pk=vencido.pk).pagado_en)

    def test_crear_pagado_directo_fija_pagado_en(self) -> None:
        antes = timezone.now()
        movimiento = self._crear(estado=Movimiento.Estado.PAGADO)
        leido = Movimiento.objects.get(pk=movimiento.pk)
        self.assertIsNotNone(leido.pagado_en)
        self.assertGreaterEqual(leido.pagado_en, antes)

    def test_constraint_rechaza_pagado_en_en_pendiente(self) -> None:
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._crear(pagado_en=timezone.now())
        self.assertEqual(Movimiento.objects.count(), 0)

    def test_constraint_rechaza_pagado_sin_pagado_en(self) -> None:
        movimiento = self._crear()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Movimiento.objects.filter(pk=movimiento.pk).update(
                    estado=Movimiento.Estado.PAGADO,
                )
        self.assertEqual(
            Movimiento.objects.get(pk=movimiento.pk).estado,
            Movimiento.Estado.PENDIENTE,
        )
        self.assertIsNone(Movimiento.objects.get(pk=movimiento.pk).pagado_en)
