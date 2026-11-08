from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase

from ambito.models import Comercio
from movimientos.correlacion import AvisoPago, aplicar_aviso
from movimientos.exceptions import AvisoInvalido, AvisoSinCobro, TransicionInvalida
from movimientos.models import Cobro, Movimiento


class CorrelacionTests(TestCase):
    def setUp(self) -> None:
        self.comercio = Comercio.objects.create(nombre="Abarrotes Centro")
        self.origen = Movimiento.Origen.ORIGEN_PEY

    def _cobro(self, **kwargs) -> Cobro:
        canal = kwargs.get("canal", Movimiento.Canal.QR_VENTA)
        datos = {
            "comercio": self.comercio,
            "canal": canal,
            "monto": (
                Decimal("0.00")
                if canal == Movimiento.Canal.QR_GENERAL
                else Decimal("25.00")
            ),
            "concepto": "Transferencia",
            "pey_qr_id": None,
            "pey_transaction_id": None,
        }
        if canal == Movimiento.Canal.NOTIFICACION:
            datos["pey_transaction_id"] = "TX-DEFAULT"
        else:
            datos["pey_qr_id"] = "QR-DEFAULT"
        datos.update(kwargs)
        return Cobro.objects.create(**datos)

    def _movimiento(self, cobro: Cobro, **kwargs) -> Movimiento:
        datos = {
            "comercio": cobro.comercio,
            "cobro": cobro,
            "monto": cobro.monto if cobro.monto > 0 else Decimal("10.00"),
            "concepto": cobro.concepto,
            "canal": cobro.canal,
            "origen": Movimiento.Origen.ORIGEN_DESARROLLO,
        }
        datos.update(kwargs)
        return Movimiento.objects.create(**datos)

    def _aviso_qr(
        self,
        codi_qr_id: str | None,
        *,
        transaction_id: str = "TX-PAGO",
        monto: Decimal = Decimal("25.00"),
        concepto: str = "lo que escribió el pagador",
    ) -> AvisoPago:
        return AvisoPago(
            tipo="codi.qr.payment_received",
            monto=monto,
            transaction_id=transaction_id,
            codi_qr_id=codi_qr_id,
            concepto=concepto,
        )

    def _aviso_pn(
        self,
        transaction_id: str,
        *,
        monto: Decimal = Decimal("25.00"),
    ) -> AvisoPago:
        return AvisoPago(
            tipo="codi.pn.payment_received",
            monto=monto,
            transaction_id=transaction_id,
            codi_qr_id=None,
        )

    def test_qr_con_codi_qr_id_ajeno_no_marca_pagado(self) -> None:
        cobro = self._cobro(canal=Movimiento.Canal.QR_VENTA, pey_qr_id="QR-A")
        movimiento = self._movimiento(cobro)

        with self.assertRaises(AvisoSinCobro):
            aplicar_aviso(self._aviso_qr("QR-OTRO"), origen=self.origen)

        leido = Movimiento.objects.get(pk=movimiento.pk)
        self.assertEqual(leido.estado, Movimiento.Estado.PENDIENTE)
        self.assertIsNone(leido.pey_transaction_id)

    def test_pn_con_transaction_id_ajeno_no_marca_pagado(self) -> None:
        cobro = self._cobro(
            canal=Movimiento.Canal.NOTIFICACION,
            pey_transaction_id="TX-A",
            pey_qr_id=None,
        )
        movimiento = self._movimiento(cobro)

        with self.assertRaises(AvisoSinCobro):
            aplicar_aviso(self._aviso_pn("TX-OTRO"), origen=self.origen)

        leido = Movimiento.objects.get(pk=movimiento.pk)
        self.assertEqual(leido.estado, Movimiento.Estado.PENDIENTE)
        self.assertIsNone(leido.pey_transaction_id)

    def test_el_aviso_solo_afecta_al_comercio_del_cobro(self) -> None:
        comercio_a = Comercio.objects.create(nombre="Comercio A")
        comercio_b = Comercio.objects.create(nombre="Comercio B")
        cobro_a = self._cobro(
            comercio=comercio_a,
            canal=Movimiento.Canal.QR_VENTA,
            pey_qr_id="QR-A",
        )
        cobro_b = self._cobro(
            comercio=comercio_b,
            canal=Movimiento.Canal.QR_VENTA,
            pey_qr_id="QR-B",
        )
        movimiento_a = self._movimiento(cobro_a)
        movimiento_b = self._movimiento(cobro_b)

        pagado = aplicar_aviso(self._aviso_qr("QR-B", transaction_id="TX-B"), origen=self.origen)

        self.assertEqual(pagado.pk, movimiento_b.pk)
        self.assertEqual(pagado.comercio_id, comercio_b.pk)
        self.assertEqual(
            Movimiento.objects.get(pk=movimiento_a.pk).estado,
            Movimiento.Estado.PENDIENTE,
        )
        self.assertEqual(
            Movimiento.objects.get(pk=movimiento_b.pk).estado,
            Movimiento.Estado.PAGADO,
        )
        self.assertEqual(comercio_a.movimientos.count(), 1)
        self.assertEqual(list(comercio_a.movimientos.values_list("pk", flat=True)), [movimiento_a.pk])

        qr_a = self._cobro(
            comercio=comercio_a,
            canal=Movimiento.Canal.QR_GENERAL,
            monto=Decimal("0.00"),
            pey_qr_id="QR-GEN-A",
        )
        qr_b = self._cobro(
            comercio=comercio_b,
            canal=Movimiento.Canal.QR_GENERAL,
            monto=Decimal("0.00"),
            pey_qr_id="QR-GEN-B",
        )
        antes_de_a = comercio_a.movimientos.count()
        nuevo = aplicar_aviso(
            self._aviso_qr("QR-GEN-B", transaction_id="TX-GEN-B", monto=Decimal("0.01")),
            origen=self.origen,
        )
        self.assertEqual(nuevo.comercio_id, comercio_b.pk)
        self.assertEqual(nuevo.cobro_id, qr_b.pk)
        self.assertEqual(comercio_a.movimientos.count(), antes_de_a)
        self.assertFalse(qr_a.movimientos.exists())
        self.assertEqual(qr_b.movimientos.count(), 1)

    def test_qr_general_guarda_el_monto_abierto_y_un_movimiento_por_pago(self) -> None:
        cobro = self._cobro(
            canal=Movimiento.Canal.QR_GENERAL,
            monto=Decimal("0.00"),
            concepto="Transferencia",
            pey_qr_id="QR-GEN",
        )

        primero = aplicar_aviso(
            self._aviso_qr(
                "QR-GEN",
                transaction_id="TX-1",
                monto=Decimal("0.01"),
                concepto="otro concepto",
            ),
            origen=self.origen,
        )
        segundo = aplicar_aviso(
            self._aviso_qr("QR-GEN", transaction_id="TX-2", monto=Decimal("0.01")),
            origen=self.origen,
        )

        self.assertNotEqual(primero.pk, segundo.pk)
        self.assertEqual(cobro.movimientos.count(), 2)
        for movimiento in cobro.movimientos.order_by("pk"):
            leido = Movimiento.objects.get(pk=movimiento.pk)
            self.assertEqual(leido.canal, Movimiento.Canal.QR_GENERAL)
            self.assertEqual(leido.estado, Movimiento.Estado.PAGADO)
            self.assertEqual(leido.monto, Decimal("0.01"))
            self.assertIsInstance(leido.monto, Decimal)
            self.assertEqual(leido.comercio_id, cobro.comercio_id)
            self.assertEqual(leido.concepto, "Transferencia")
            self.assertEqual(leido.concepto_visible, "Transferencia")
            self.assertEqual(leido.origen, self.origen)
        self.assertEqual(
            {primero.pey_transaction_id, segundo.pey_transaction_id},
            {"TX-1", "TX-2"},
        )

    def test_el_aviso_con_el_id_correcto_marca_pagado(self) -> None:
        venta = self._cobro(canal=Movimiento.Canal.QR_VENTA, pey_qr_id="QR-VENTA")
        movimiento_venta = self._movimiento(venta)
        pagado_venta = aplicar_aviso(
            self._aviso_qr("QR-VENTA", transaction_id="TX-VENTA", monto=Decimal("1.00")),
            origen=self.origen,
        )
        self.assertEqual(pagado_venta.pk, movimiento_venta.pk)
        leido_venta = Movimiento.objects.get(pk=movimiento_venta.pk)
        self.assertEqual(leido_venta.estado, Movimiento.Estado.PAGADO)
        self.assertEqual(leido_venta.pey_transaction_id, "TX-VENTA")
        self.assertEqual(leido_venta.monto, Decimal("25.00"))
        self.assertEqual(leido_venta.origen, Movimiento.Origen.ORIGEN_DESARROLLO)

        notificacion = self._cobro(
            canal=Movimiento.Canal.NOTIFICACION,
            pey_transaction_id="TX-PN",
            pey_qr_id=None,
        )
        movimiento_pn = self._movimiento(notificacion)
        pagado_pn = aplicar_aviso(
            self._aviso_pn("TX-PN", monto=Decimal("99.00")),
            origen=self.origen,
        )
        self.assertEqual(pagado_pn.pk, movimiento_pn.pk)
        leido_pn = Movimiento.objects.get(pk=movimiento_pn.pk)
        self.assertEqual(leido_pn.estado, Movimiento.Estado.PAGADO)
        self.assertEqual(leido_pn.pey_transaction_id, "TX-PN")
        self.assertEqual(leido_pn.comercio_id, notificacion.comercio_id)

    def test_aviso_sobre_vencido_no_marca_pagado(self) -> None:
        casos = (
            (
                self._cobro(canal=Movimiento.Canal.QR_VENTA, pey_qr_id="QR-VENCIDO"),
                self._aviso_qr("QR-VENCIDO", transaction_id="TX-TARDE"),
            ),
            (
                self._cobro(
                    canal=Movimiento.Canal.NOTIFICACION,
                    pey_transaction_id="TX-VENCIDA",
                    pey_qr_id=None,
                ),
                self._aviso_pn("TX-VENCIDA"),
            ),
        )
        for cobro, aviso in casos:
            movimiento = self._movimiento(cobro)
            movimiento.cambiar_estado(Movimiento.Estado.VENCIDO)
            with self.assertRaises(TransicionInvalida):
                aplicar_aviso(aviso, origen=self.origen)
            leido = Movimiento.objects.get(pk=movimiento.pk)
            self.assertEqual(leido.estado, Movimiento.Estado.VENCIDO)
            self.assertIsNone(leido.pey_transaction_id)

    def test_constraints_de_cobro_rechazan_monto_e_ids_incoherentes(self) -> None:
        rechazados = (
            {
                "canal": Movimiento.Canal.QR_GENERAL,
                "monto": Decimal("10.00"),
                "pey_qr_id": "QR-MONTO",
            },
            {
                "canal": Movimiento.Canal.QR_VENTA,
                "monto": Decimal("0.00"),
                "pey_qr_id": "QR-CERO",
            },
            {
                "canal": Movimiento.Canal.QR_GENERAL,
                "monto": Decimal("0.00"),
                "pey_qr_id": None,
            },
            {
                "canal": Movimiento.Canal.QR_VENTA,
                "monto": Decimal("10.00"),
                "pey_qr_id": None,
            },
            {
                "canal": Movimiento.Canal.NOTIFICACION,
                "monto": Decimal("10.00"),
                "pey_transaction_id": None,
            },
            {
                "canal": Movimiento.Canal.QR_VENTA,
                "monto": Decimal("10.00"),
                "pey_qr_id": "QR-AMBOS",
                "pey_transaction_id": "TX-AMBOS",
            },
            {
                "canal": Movimiento.Canal.NOTIFICACION,
                "monto": Decimal("10.00"),
                "pey_qr_id": "QR-PN",
                "pey_transaction_id": "TX-PN-MAL",
            },
        )
        for datos in rechazados:
            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    self._cobro(**datos)
        self.assertEqual(Cobro.objects.count(), 0)

        self._cobro(
            canal=Movimiento.Canal.QR_GENERAL,
            monto=Decimal("0.00"),
            pey_qr_id="QR-OK",
        )
        self._cobro(
            canal=Movimiento.Canal.QR_VENTA,
            monto=Decimal("10.00"),
            pey_qr_id="QR-VENTA-OK",
        )
        self._cobro(
            canal=Movimiento.Canal.NOTIFICACION,
            monto=Decimal("10.00"),
            pey_transaction_id="TX-OK",
            pey_qr_id=None,
        )
        self.assertEqual(Cobro.objects.count(), 3)

    def test_un_id_del_otro_canal_no_correlaciona(self) -> None:
        notificacion = self._cobro(
            canal=Movimiento.Canal.NOTIFICACION,
            pey_transaction_id="TX-SOLO-PN",
            pey_qr_id=None,
        )
        movimiento_pn = self._movimiento(notificacion)
        with self.assertRaises(AvisoSinCobro):
            aplicar_aviso(self._aviso_qr("TX-SOLO-PN"), origen=self.origen)
        self.assertEqual(
            Movimiento.objects.get(pk=movimiento_pn.pk).estado,
            Movimiento.Estado.PENDIENTE,
        )

        venta = self._cobro(canal=Movimiento.Canal.QR_VENTA, pey_qr_id="QR-SOLO")
        movimiento_qr = self._movimiento(venta)
        with self.assertRaises(AvisoSinCobro):
            aplicar_aviso(self._aviso_pn("QR-SOLO"), origen=self.origen)
        self.assertEqual(
            Movimiento.objects.get(pk=movimiento_qr.pk).estado,
            Movimiento.Estado.PENDIENTE,
        )

    def test_tipo_desconocido_es_aviso_invalido(self) -> None:
        aviso = AvisoPago(
            tipo="codi.qr.rejected",
            monto=Decimal("1.00"),
            transaction_id="TX-RARO",
            codi_qr_id="QR-RARO",
        )
        with self.assertRaises(AvisoInvalido):
            aplicar_aviso(aviso, origen=self.origen)
        self.assertEqual(Movimiento.objects.count(), 0)

    def test_sin_movimiento_ligado_es_aviso_sin_cobro(self) -> None:
        self._cobro(canal=Movimiento.Canal.QR_VENTA, pey_qr_id="QR-SOLO-COBRO")
        with self.assertRaises(AvisoSinCobro):
            aplicar_aviso(self._aviso_qr("QR-SOLO-COBRO"), origen=self.origen)

        self._cobro(
            canal=Movimiento.Canal.NOTIFICACION,
            pey_transaction_id="TX-SOLO-COBRO",
            pey_qr_id=None,
        )
        with self.assertRaises(AvisoSinCobro):
            aplicar_aviso(self._aviso_pn("TX-SOLO-COBRO"), origen=self.origen)
        self.assertEqual(Movimiento.objects.count(), 0)

    def test_canal_o_comercio_distinto_al_cobro_lo_rechaza_el_modelo(self) -> None:
        cobro = self._cobro(canal=Movimiento.Canal.QR_VENTA, pey_qr_id="QR-COHERENCIA")
        otro = Comercio.objects.create(nombre="Otro comercio")
        with self.assertRaises(ValueError):
            self._movimiento(cobro, canal=Movimiento.Canal.NOTIFICACION)
        with self.assertRaises(ValueError):
            self._movimiento(cobro, comercio=otro)
        self.assertEqual(Movimiento.objects.count(), 0)

    def test_el_mismo_transaction_id_no_crea_dos_movimientos(self) -> None:
        cobro = self._cobro(
            canal=Movimiento.Canal.QR_GENERAL,
            monto=Decimal("0.00"),
            pey_qr_id="QR-UNICO",
        )
        aplicar_aviso(
            self._aviso_qr("QR-UNICO", transaction_id="TX-REPETIDO", monto=Decimal("0.01")),
            origen=self.origen,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                aplicar_aviso(
                    self._aviso_qr(
                        "QR-UNICO",
                        transaction_id="TX-REPETIDO",
                        monto=Decimal("0.01"),
                    ),
                    origen=self.origen,
                )
        self.assertEqual(cobro.movimientos.count(), 1)
        self.assertEqual(
            cobro.movimientos.get().estado,
            Movimiento.Estado.PAGADO,
        )
