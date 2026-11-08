import ast
import importlib
import inspect
from decimal import Decimal
from unittest.mock import patch

from django.test import SimpleTestCase

from ambito.models import Comercio

from pey.desarrollo import AdaptadorDesarrollo
from pey.produccion import AdaptadorProduccion
from pey.tipos import ErrorPey, ParametroInvalido


def _revienta(*args, **kwargs):
    raise AssertionError("no debe haber red")


class DesarrolloSinRedTests(SimpleTestCase):
    def test_crea_qr_pn_y_cuenta_active_sin_salir_a_la_red(self) -> None:
        with (
            patch("socket.socket.connect", _revienta),
            patch("urllib.request.urlopen", _revienta),
        ):
            adaptador = AdaptadorDesarrollo()
            qr = adaptador.crear_qr(monto=Decimal("15.50"), concepto="Tacos")
            aviso = adaptador.crear_notificacion(
                monto=Decimal("15.50"),
                telefono="5512345678",
                concepto="Tacos",
            )
            comercio = Comercio(nombre="Demo", semilla_active_dev=True)
            self.assertTrue(adaptador.cuenta_active(comercio))

        self.assertTrue(qr.id.startswith("dev-qr-"))
        self.assertEqual(len(qr.id.removeprefix("dev-qr-")), 32)
        self.assertEqual(qr.qr_string, f"cody-dev://qr/{qr.id}")
        self.assertTrue(aviso.transaction_id.startswith("dev-tx-"))
        self.assertEqual(len(aviso.transaction_id.removeprefix("dev-tx-")), 32)
        self.assertRegex(aviso.codi_id, r"^[0-9]{20}$")

    def test_acepta_ulid_y_rechaza_uno_invalido_sin_red(self) -> None:
        with patch("urllib.request.urlopen", _revienta):
            adaptador = AdaptadorDesarrollo()
            qr = adaptador.crear_qr(
                monto=Decimal("0.01"),
                bank_account_id="01ARZ3NDEKTSV4RRFFQ69G5FAV",
            )
            self.assertTrue(qr.id.startswith("dev-qr-"))
            with self.assertRaises(ParametroInvalido):
                adaptador.crear_notificacion(
                    monto=Decimal("0.01"),
                    telefono="5512345678",
                    bank_account_id="no-es-ulid",
                )

    def test_el_modulo_no_importa_red_ni_lee_secretos(self) -> None:
        import pey.desarrollo as desarrollo

        importlib.reload(desarrollo)
        fuente = inspect.getsource(desarrollo)
        for prohibido in (
            "urllib",
            "requests",
            "http.client",
            "socket",
            "urlopen",
            "PEY_API_KEY",
            "PEY_WEBHOOK_SECRET",
            "api.pey.mx",
        ):
            self.assertNotIn(prohibido, fuente)

        modulos = set()
        for nodo in ast.walk(ast.parse(fuente)):
            if isinstance(nodo, ast.Import):
                modulos.update(alias.name.split(".")[0] for alias in nodo.names)
            elif isinstance(nodo, ast.ImportFrom) and nodo.module:
                modulos.add(nodo.module.split(".")[0])
        self.assertTrue(
            modulos.isdisjoint({"urllib", "requests", "http", "socket"})
        )
        self.assertFalse(
            {"urllib", "requests", "http", "socket"} & set(vars(desarrollo))
        )


class CuentaActiveTests(SimpleTestCase):
    def test_produccion_ignora_la_semilla_y_desarrollo_la_usa(self) -> None:
        def transporte(*args, **kwargs):
            raise AssertionError("cuenta_active no usa el transporte")

        con_semilla = Comercio(nombre="Con semilla", semilla_active_dev=True)
        sin_semilla = Comercio(nombre="Sin semilla", semilla_active_dev=False)

        self.assertFalse(
            AdaptadorProduccion(transporte=transporte).cuenta_active(con_semilla)
        )
        self.assertTrue(AdaptadorDesarrollo().cuenta_active(con_semilla))
        self.assertFalse(AdaptadorDesarrollo().cuenta_active(sin_semilla))

        import pey.produccion as produccion

        self.assertNotIn("semilla_active_dev", inspect.getsource(produccion))
        self.assertIn(
            "cuenta_esta_active",
            inspect.getsource(AdaptadorProduccion.cuenta_active),
        )


class CuerpoAvisoQrPagadoTests(SimpleTestCase):
    def test_plantilla_compatible_y_ids_distintos(self) -> None:
        adaptador = AdaptadorDesarrollo()
        primero = adaptador.cuerpo_aviso_qr_pagado(
            monto=Decimal("0.01"),
            codi_qr_id="dev-qr-abc",
        )
        segundo = adaptador.cuerpo_aviso_qr_pagado(
            monto=Decimal("0.02"),
            codi_qr_id="dev-qr-abc",
        )
        self.assertEqual(primero["type"], "codi.qr.payment_received")
        self.assertEqual(primero["codiQrId"], "dev-qr-abc")
        self.assertEqual(primero["amount"], Decimal("0.01"))
        self.assertEqual(segundo["amount"], Decimal("0.02"))
        self.assertNotEqual(primero["transactionId"], segundo["transactionId"])
        self.assertTrue(str(primero["transactionId"]).startswith("dev-tx-"))

    def test_transaction_id_explicito_y_validaciones(self) -> None:
        adaptador = AdaptadorDesarrollo()
        cuerpo = adaptador.cuerpo_aviso_qr_pagado(
            monto=Decimal("1.50"),
            codi_qr_id="dev-qr-x",
            transaction_id="TX-FIJO-H3",
        )
        self.assertEqual(cuerpo["transactionId"], "TX-FIJO-H3")

        with self.assertRaises(ParametroInvalido):
            adaptador.cuerpo_aviso_qr_pagado(
                monto=Decimal("0"),
                codi_qr_id="dev-qr-x",
            )
        with self.assertRaises(ParametroInvalido):
            adaptador.cuerpo_aviso_qr_pagado(
                monto=Decimal("0.01"),
                codi_qr_id="",
            )


class FallarConTests(SimpleTestCase):
    def test_el_error_sale_despues_de_validar(self) -> None:
        error = ErrorPey("INVALID_STATE", "simulada", "req-dev")
        adaptador = AdaptadorDesarrollo(fallar_con=error)

        with self.assertRaises(ParametroInvalido):
            adaptador.crear_qr(monto=Decimal("-1"))
        with self.assertRaises(ParametroInvalido):
            adaptador.crear_notificacion(monto=Decimal("0"), telefono="5512345678")

        with self.assertRaises(ErrorPey) as qr:
            adaptador.crear_qr(monto=Decimal("10"))
        self.assertIs(qr.exception, error)

        with self.assertRaises(ErrorPey) as aviso:
            adaptador.crear_notificacion(monto=Decimal("10"), telefono="5512345678")
        self.assertIs(aviso.exception, error)

        comercio = Comercio(nombre="Demo", semilla_active_dev=True)
        self.assertTrue(adaptador.cuenta_active(comercio))
