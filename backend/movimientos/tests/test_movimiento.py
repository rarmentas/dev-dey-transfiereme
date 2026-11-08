from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase

from ambito.models import Comercio
from movimientos.exceptions import TransicionInvalida
from movimientos.models import Movimiento


class MovimientoTests(TestCase):
    def setUp(self) -> None:
        self.comercio = Comercio.objects.create(nombre="Abarrotes Centro")

    def _crear(self, **kwargs) -> Movimiento:
        datos = {
            "comercio": self.comercio,
            "monto": Decimal("10.00"),
            "concepto": "Transferencia",
            "canal": Movimiento.Canal.QR_GENERAL,
            "origen": Movimiento.Origen.ORIGEN_DESARROLLO,
        }
        datos.update(kwargs)
        return Movimiento.objects.create(**datos)

    def test_tres_canales_se_crean_y_se_leen(self) -> None:
        canales = (
            Movimiento.Canal.QR_GENERAL,
            Movimiento.Canal.QR_VENTA,
            Movimiento.Canal.NOTIFICACION,
        )
        for canal in canales:
            self._crear(canal=canal, concepto=f"Cobro {canal}")

        leidos = {
            movimiento.canal: movimiento
            for movimiento in self.comercio.movimientos.all()
        }
        self.assertEqual(set(leidos), set(canales))
        for canal in canales:
            self.assertEqual(leidos[canal].estado, Movimiento.Estado.PENDIENTE)
            self.assertEqual(leidos[canal].concepto_visible, f"Cobro {canal}")
            self.assertEqual(leidos[canal].concepto, f"Cobro {canal}")

    def test_monto_un_centavo_persiste_exacto(self) -> None:
        movimiento = self._crear(monto=Decimal("0.01"))
        leido = Movimiento.objects.get(pk=movimiento.pk)
        self.assertIsInstance(leido.monto, Decimal)
        self.assertEqual(leido.monto, Decimal("0.01"))

    def test_pendiente_pasa_a_pagado_y_a_vencido(self) -> None:
        pagado = self._crear()
        pagado.cambiar_estado(Movimiento.Estado.PAGADO)
        self.assertEqual(
            Movimiento.objects.get(pk=pagado.pk).estado,
            Movimiento.Estado.PAGADO,
        )

        vencido = self._crear()
        vencido.cambiar_estado(Movimiento.Estado.VENCIDO)
        self.assertEqual(
            Movimiento.objects.get(pk=vencido.pk).estado,
            Movimiento.Estado.VENCIDO,
        )

    def test_pagado_no_vuelve_a_pendiente_ni_a_vencido(self) -> None:
        movimiento = self._crear()
        movimiento.cambiar_estado(Movimiento.Estado.PAGADO)
        for destino in (
            Movimiento.Estado.PENDIENTE,
            Movimiento.Estado.VENCIDO,
            Movimiento.Estado.PAGADO,
        ):
            with self.assertRaises(TransicionInvalida):
                movimiento.cambiar_estado(destino)
        self.assertEqual(
            Movimiento.objects.get(pk=movimiento.pk).estado,
            Movimiento.Estado.PAGADO,
        )

    def test_vencido_pasa_a_pagado_y_fija_pagado_en(self) -> None:
        movimiento = self._crear()
        movimiento.cambiar_estado(Movimiento.Estado.VENCIDO)
        self.assertIsNone(Movimiento.objects.get(pk=movimiento.pk).pagado_en)
        movimiento.cambiar_estado(Movimiento.Estado.PAGADO)
        leido = Movimiento.objects.get(pk=movimiento.pk)
        self.assertEqual(leido.estado, Movimiento.Estado.PAGADO)
        self.assertIsNotNone(leido.pagado_en)
        for destino in (
            Movimiento.Estado.PENDIENTE,
            Movimiento.Estado.VENCIDO,
            Movimiento.Estado.PAGADO,
        ):
            with self.assertRaises(TransicionInvalida):
                movimiento.cambiar_estado(destino)
        self.assertEqual(leido.estado, Movimiento.Estado.PAGADO)

    def test_misma_transicion_desde_pendiente_falla(self) -> None:
        movimiento = self._crear()
        with self.assertRaises(TransicionInvalida):
            movimiento.cambiar_estado(Movimiento.Estado.PENDIENTE)
        self.assertEqual(
            Movimiento.objects.get(pk=movimiento.pk).estado,
            Movimiento.Estado.PENDIENTE,
        )

    def test_save_directo_no_cambia_estado(self) -> None:
        movimiento = self._crear()
        movimiento.estado = Movimiento.Estado.PAGADO
        with self.assertRaises(TransicionInvalida):
            movimiento.save()
        with self.assertRaises(TransicionInvalida):
            movimiento.save(update_fields=["estado", "actualizado_en"])
        self.assertEqual(
            Movimiento.objects.get(pk=movimiento.pk).estado,
            Movimiento.Estado.PENDIENTE,
        )

    def test_concepto_visible_se_edita_sin_cambiar_el_de_pey(self) -> None:
        movimiento = self._crear(concepto="Transferencia")
        movimiento.concepto_visible = "Tacos de la esquina"
        movimiento.save()
        leido = Movimiento.objects.get(pk=movimiento.pk)
        self.assertEqual(leido.concepto, "Transferencia")
        self.assertEqual(leido.concepto_visible, "Tacos de la esquina")
        self.assertEqual(leido.estado, Movimiento.Estado.PENDIENTE)

    def test_monto_cero_o_negativo_lo_rechaza_la_base(self) -> None:
        for monto in (Decimal("0"), Decimal("0.00"), Decimal("-0.01"), Decimal("-1")):
            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    self._crear(monto=monto)
        self.assertEqual(Movimiento.objects.count(), 0)

    def test_canal_invalido_lo_rechaza_la_base(self) -> None:
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._crear(canal="nfc")
        self.assertEqual(Movimiento.objects.count(), 0)

    def test_estado_invalido_lo_rechaza_la_base(self) -> None:
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._crear(estado="raro")
        self.assertEqual(Movimiento.objects.count(), 0)

    def test_origen_invalido_lo_rechaza_la_base(self) -> None:
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._crear(origen="otro")
        self.assertEqual(Movimiento.objects.count(), 0)

    def test_origen_acepta_pey_y_desarrollo(self) -> None:
        pey = self._crear(origen=Movimiento.Origen.ORIGEN_PEY)
        desarrollo = self._crear(origen=Movimiento.Origen.ORIGEN_DESARROLLO)
        self.assertEqual(
            Movimiento.objects.get(pk=pey.pk).origen,
            Movimiento.Origen.ORIGEN_PEY,
        )
        self.assertEqual(
            Movimiento.objects.get(pk=desarrollo.pk).origen,
            Movimiento.Origen.ORIGEN_DESARROLLO,
        )
