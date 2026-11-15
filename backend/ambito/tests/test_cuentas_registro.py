from datetime import timedelta
from unittest.mock import patch

from django.db import connection
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from ambito.cuenta import cuenta_esta_active
from ambito.cuentas_servicio import alta
from ambito.models import Comercio, CuentaCobro, OperacionCuenta
from ambito.operaciones_cuenta import (
    ErrorOperacion,
    _aplicar,
    recuperar_abandonadas,
    registrar,
    sincronizar,
)
from ambito.tests.soporte import clabe_valida, crear_cuenta
from pey.cuentas import CuentaPey
from pey.tipos import ErrorPey


class CuentasRegistroAcTests(TestCase):
    def test_ac1_16_estado_por_cuenta_es_independiente(self):
        comercio = Comercio.objects.create(nombre="A")
        activa = crear_cuenta(comercio)
        pendiente = crear_cuenta(comercio, estado="pending", predeterminada=False)
        self.assertTrue(cuenta_esta_active(comercio))
        activa.codi_status = "pending"
        activa.save(update_fields=["codi_status"])
        pendiente.codi_status = "active"
        pendiente.save(update_fields=["codi_status"])
        self.assertFalse(cuenta_esta_active(comercio))
        comercio.refresh_from_db()
        self.assertEqual(comercio.cuenta_por_defecto_id, activa.pk)

    def test_sync_active_con_clabe_distinta_no_habilita_cobro(self):
        comercio = Comercio.objects.create(nombre="Desajuste")
        cuenta = crear_cuenta(comercio)
        with patch(
            "ambito.operaciones_cuenta.consultar_cuenta",
            return_value=CuentaPey(
                cuenta.pey_bank_account_id, "ACTIVE", clabe_valida(2)
            ),
        ):
            sincronizar(cuenta)
        cuenta.refresh_from_db()
        self.assertEqual(cuenta.codi_status, "pending")
        self.assertEqual(cuenta.anomalia, "CLABE_NO_COINCIDE")
        self.assertFalse(cuenta_esta_active(comercio))
        self.assertEqual(comercio.cuenta_por_defecto_id, cuenta.pk)

    def test_id_duplicado_en_respuesta_deja_registro_incierto(self):
        comercio = Comercio.objects.create(nombre="B")
        cuenta = crear_cuenta(comercio, estado="pending", predeterminada=False)
        cuenta.pey_bank_account_id = ""
        cuenta.registro_estado = "sin_registro"
        cuenta.save(update_fields=["pey_bank_account_id", "registro_estado"])
        otra = crear_cuenta(Comercio.objects.create(nombre="C"))
        with (
            patch("ambito.operaciones_cuenta.exigir_modo_produccion"),
            patch(
                "ambito.operaciones_cuenta.registrar_cuenta",
                return_value=CuentaPey(otra.pey_bank_account_id, "ACTIVE"),
            ) as llamada,
        ):
            with self.assertRaises(ErrorOperacion) as error:
                registrar(
                    cuenta,
                    nombre="Ana",
                    entidad="PERSON",
                    alias="",
                    clave="k",
                    version=cuenta.version,
                )
            self.assertEqual(error.exception.codigo, "PEY_INCIERTO")
            with self.assertRaises(ErrorOperacion):
                registrar(
                    cuenta,
                    nombre="Ana",
                    entidad="PERSON",
                    alias="",
                    clave="k",
                    version=cuenta.version,
                )
            llamada.assert_called_once()
        cuenta.refresh_from_db()
        self.assertEqual(cuenta.registro_estado, "incierto")
        self.assertEqual(cuenta.pey_bank_account_id, "")
        otra.refresh_from_db()
        self.assertEqual(otra.codi_status, "active")


class RegistroCriticoTests(TestCase):
    def setUp(self):
        self.comercio = Comercio.objects.create(nombre="A")

    def test_registro_abandonado_pasa_a_incierto(self):
        cuenta = alta(self.comercio, clabe_valida(1))
        cuenta.registro_estado = "registrando"
        cuenta.save(update_fields=["registro_estado"])
        op = OperacionCuenta.objects.create(
            cuenta=cuenta,
            tipo="registro",
            origen="ui",
            estado="en_curso",
            version_reclamada=cuenta.version,
            lease_hasta=timezone.now() - timedelta(seconds=1),
        )
        recuperar_abandonadas()
        cuenta.refresh_from_db()
        op.refresh_from_db()
        self.assertEqual(cuenta.registro_estado, "incierto")
        self.assertEqual(op.estado, "incierta")

    @override_settings(PEY_ADAPTADOR="produccion")
    def test_timeout_de_registro_sin_id_queda_incierto_sin_repetir_post(self):
        cuenta = alta(self.comercio, clabe_valida(1))
        with (
            patch("ambito.operaciones_cuenta.exigir_modo_produccion"),
            patch(
                "ambito.operaciones_cuenta.registrar_cuenta",
                side_effect=ErrorPey("NO_DISPONIBLE", "", puede_haberse_creado=True),
            ) as llamada,
        ):
            for codigo in ("PEY_INCIERTO", "REGISTRO_INCIERTO"):
                with self.assertRaises(ErrorOperacion) as capturada:
                    registrar(
                        cuenta,
                        nombre="Nombre",
                        entidad="PERSON",
                        alias="",
                        clave="clave",
                        version=1,
                    )
                self.assertEqual(capturada.exception.codigo, codigo)
            self.assertEqual(llamada.call_count, 1)
        cuenta.refresh_from_db()
        self.assertEqual(cuenta.registro_estado, "incierto")
        self.assertEqual(cuenta.pey_bank_account_id, "")

    def test_sync_con_version_vieja_no_pisa_la_nueva(self):
        cuenta = crear_cuenta(self.comercio)
        op = OperacionCuenta.objects.create(
            cuenta=cuenta,
            tipo="sync",
            origen="ui",
            estado="en_curso",
            version_reclamada=1,
        )
        CuentaCobro.objects.filter(pk=cuenta.pk).update(version=2, codi_status="active")
        _aplicar(op, {"codi_status": "pending"}, "aplicada")
        cuenta.refresh_from_db()
        op.refresh_from_db()
        self.assertEqual(cuenta.codi_status, "active")
        self.assertEqual(op.estado, "descartada")


class OperacionesSinCandadoTests(TransactionTestCase):
    def test_registro_y_sync_consultan_fuera_de_transaccion(self):
        comercio = Comercio.objects.create(nombre="Sin candados")
        cuenta = crear_cuenta(comercio, estado="pending", predeterminada=False)
        cuenta.pey_bank_account_id = ""
        cuenta.registro_estado = "sin_registro"
        cuenta.save(update_fields=["pey_bank_account_id", "registro_estado"])
        ident = "01J9ZQ4C8X7Y6W5V4T3S2R1Q0P"

        def respuesta(**kwargs):
            self.assertFalse(connection.in_atomic_block)
            return CuentaPey(ident, "PENDING")

        with (
            patch("ambito.operaciones_cuenta.exigir_modo_produccion"),
            patch("ambito.operaciones_cuenta.registrar_cuenta", side_effect=respuesta),
        ):
            registrar(
                cuenta,
                nombre="Ana",
                entidad="PERSON",
                alias="",
                clave="a",
                version=cuenta.version,
            )
        cuenta.refresh_from_db()

        def consulta(*args, **kwargs):
            self.assertFalse(connection.in_atomic_block)
            return CuentaPey(ident, "ACTIVE", cuenta.clabe)

        with patch("ambito.operaciones_cuenta.consultar_cuenta", side_effect=consulta):
            sincronizar(cuenta)
        cuenta.refresh_from_db()
        self.assertEqual(cuenta.codi_status, "active")
