"""Comandos de cuenta sin red ni salida sensible."""

from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from ambito.models import Comercio, Membresia
from ambito.tests.soporte import crear_cuenta
from pey.cuentas import CuentaPey
from pey.tipos import ErrorPey

_ID = "01J9ZQ4C8X7Y6W5V4T3S2R1Q0P"


@override_settings(DEBUG=True, PEY_ADAPTADOR="produccion", PEY_API_KEY="prueba")
class ComandosPeyTests(TestCase):
    def setUp(self) -> None:
        self.comercio = Comercio.objects.create(nombre="Tienda")
        self.cuenta = crear_cuenta(
            self.comercio, estado="pending", predeterminada=False
        )
        self.cuenta.pey_bank_account_id = ""
        self.cuenta.registro_estado = "sin_registro"
        self.cuenta.save(update_fields=["pey_bank_account_id", "registro_estado"])
        usuario = User.objects.create_user(username="ana", email="ana@ejemplo.mx")
        Membresia.objects.create(usuario=usuario, comercio=self.comercio, es_dueno=True)

    def _registrar(self, **opciones):
        return call_command("registrar_cuenta_pey", correo="ana@ejemplo.mx",
                            cuenta=str(self.cuenta.pk), nombre="Ana", entidad="PERSON",
                            **opciones)

    def test_sin_confirmar_no_llama(self) -> None:
        salida = StringIO()
        with patch("ambito.operaciones_cuenta.registrar_cuenta") as llamada:
            self._registrar(stdout=salida)
        llamada.assert_not_called()
        self.assertIn("Sin --confirmar", salida.getvalue())
        self.assertNotIn(self.cuenta.clabe, salida.getvalue())

    def test_confirmar_guarda_el_id(self) -> None:
        with patch("ambito.operaciones_cuenta.registrar_cuenta",
                   return_value=CuentaPey(_ID, "ACTIVE")) as llamada:
            self._registrar(confirmar=True, stdout=StringIO())
        llamada.assert_called_once()
        self.cuenta.refresh_from_db()
        self.assertEqual(self.cuenta.pey_bank_account_id, _ID)
        self.assertEqual(self.cuenta.codi_status, "active")

    @override_settings(DEBUG=True, PEY_ADAPTADOR="desarrollo", PEY_API_KEY="")
    def test_se_niega_en_desarrollo(self) -> None:
        with patch("ambito.operaciones_cuenta.registrar_cuenta") as llamada:
            with self.assertRaises(CommandError):
                self._registrar(confirmar=True, stdout=StringIO())
        llamada.assert_not_called()

    def test_confirmar_conserva_codi_status_crudo_de_pey(self) -> None:
        with patch("ambito.operaciones_cuenta.registrar_cuenta",
                   return_value=CuentaPey(_ID, "PROCESSING")):
            self._registrar(confirmar=True, stdout=StringIO())
        self.cuenta.refresh_from_db()
        self.assertEqual(self.cuenta.codi_status_crudo, "PROCESSING")
        self.assertEqual(self.cuenta.codi_status, "pending")

    def test_diagnostico_no_imprime_secretos_y_sincroniza(self) -> None:
        self.cuenta.pey_bank_account_id = _ID
        self.cuenta.registro_estado = "registrado"
        self.cuenta.save(update_fields=["pey_bank_account_id", "registro_estado"])
        self.comercio.cuenta_por_defecto = self.cuenta
        self.comercio.save(update_fields=["cuenta_por_defecto"])
        salida = StringIO()
        with patch("ambito.operaciones_cuenta.consultar_cuenta",
                   return_value=CuentaPey(_ID, "ACTIVE", self.cuenta.clabe)):
            call_command("diagnostico_pey", correo="ana@ejemplo.mx", stdout=salida)
        self.cuenta.refresh_from_db()
        self.assertEqual(self.cuenta.codi_status, "active")
        self.assertNotIn(self.cuenta.clabe, salida.getvalue())
        self.assertNotIn(_ID, salida.getvalue())

    def test_registro_repetido_no_imprime_la_clabe(self) -> None:
        with patch("ambito.operaciones_cuenta.registrar_cuenta",
                   return_value=CuentaPey(_ID, "ACTIVE")):
            self._registrar(confirmar=True, stdout=StringIO())
        salida = StringIO()
        with self.assertRaises(CommandError):
            self._registrar(confirmar=True, stdout=salida)
        self.assertNotIn(self.cuenta.clabe, salida.getvalue())

    def test_diagnostico_imprime_el_fallo_sin_cambiar_el_estado(self) -> None:
        self.cuenta.pey_bank_account_id = _ID
        self.cuenta.registro_estado = "registrado"
        self.cuenta.codi_status = "active"
        self.cuenta.save()
        self.comercio.cuenta_por_defecto = self.cuenta
        self.comercio.save(update_fields=["cuenta_por_defecto"])
        salida = StringIO()
        with patch("ambito.operaciones_cuenta.consultar_cuenta",
                   side_effect=ErrorPey("NO_DISPONIBLE", "fallo")):
            call_command("diagnostico_pey", correo="ana@ejemplo.mx", stdout=salida)
        self.assertIn("NO_DISPONIBLE", salida.getvalue())
        self.cuenta.refresh_from_db()
        self.assertEqual(self.cuenta.codi_status, "active")
        self.assertEqual(self.cuenta.ultimo_error, "NO_DISPONIBLE")
