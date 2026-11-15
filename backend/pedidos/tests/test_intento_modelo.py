"""Restricciones de persistencia de los intentos de cobro."""

from ambito.tests.soporte import crear_comercio_con_cuenta_activa
from django.db import IntegrityError, transaction
from django.test import TestCase

from pedidos.models import IntentoCobro


class IntentoModeloTests(TestCase):
    def setUp(self):
        self.comercio = crear_comercio_con_cuenta_activa()
        self.cuenta = self.comercio.cuenta_por_defecto

    def crear_intento(self, **cambios):
        datos = {
            "origen": "legado",
            "comercio": self.comercio,
            "canal": "qr_venta",
            "estado": "reservado",
            "importe_efectivo_centavos": 100,
            "demo_mode": False,
            "politica_cobro_version": "normal-1",
            "cuenta": self.cuenta,
            "pey_bank_account_id": self.cuenta.pey_bank_account_id,
            "concepto": "Venta",
            "expiracion_s": 600,
            "clave_legado": "clave-1",
        }
        datos.update(cambios)
        return IntentoCobro.objects.create(**datos)

    def test_destino_historico_es_inmutable(self):
        intento = self.crear_intento()
        intento.pey_bank_account_id = "otro"
        with self.assertRaises(ValueError):
            intento.save()
        intento.refresh_from_db()
        self.assertEqual(intento.pey_bank_account_id, self.cuenta.pey_bank_account_id)

    def test_solo_un_intento_vivo_por_comercio(self):
        self.crear_intento()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.crear_intento(clave_legado="clave-2", estado="incierto")
        self.assertEqual(IntentoCobro.objects.count(), 1)

    def test_origen_legado_requiere_clave(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.crear_intento(clave_legado="")
        self.assertFalse(IntentoCobro.objects.exists())

    def test_demo_exige_un_centavo(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.crear_intento(demo_mode=True)
        self.assertFalse(IntentoCobro.objects.exists())

    def test_destino_sin_cuenta_solo_para_demo(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.crear_intento(cuenta=None)
        intento = self.crear_intento(
            cuenta=None, demo_mode=True, importe_efectivo_centavos=1,
            politica_cobro_version="demo-1",
        )
        self.assertIsNone(intento.cuenta_id)
        self.assertEqual(intento.importe_efectivo_centavos, 1)
        intento.demo_mode = False
        with self.assertRaises(ValueError):
            intento.save()
