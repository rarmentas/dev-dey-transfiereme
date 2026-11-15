from io import StringIO
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import RequestFactory, TestCase

from ambito.models import Comercio, CuentaCobro, Membresia
from ambito.tests.soporte import crear_cuenta
from pey.cuentas import CuentaPey


class DuenoYEnlaceTests(TestCase):
    def setUp(self) -> None:
        self.usuario = User.objects.create_user(
            username="dueño", email="dueno@ejemplo.mx"
        )
        self.comercio = Comercio.objects.create(nombre="Local")
        self.membresia = Membresia.objects.create(
            usuario=self.usuario, comercio=self.comercio
        )

    def test_designar_dueno_y_quitar(self) -> None:
        with self.assertLogs(
            "ambito.management.commands.designar_dueno", level="WARNING"
        ):
            call_command("designar_dueno", correo=self.usuario.email)
        self.membresia.refresh_from_db()
        self.assertTrue(self.membresia.es_dueno)
        with self.assertLogs(
            "ambito.management.commands.designar_dueno", level="WARNING"
        ):
            call_command("designar_dueno", correo=self.usuario.email, quitar=True)
        self.membresia.refresh_from_db()
        self.assertFalse(self.membresia.es_dueno)

    def test_admin_no_expone_legado_ni_cambia_default(self) -> None:
        self.usuario.is_staff = True
        self.usuario.is_superuser = True
        self.usuario.save(update_fields=["is_staff", "is_superuser"])
        request = RequestFactory().get("/admin/")
        request.user = self.usuario
        formulario = admin.site._registry[Comercio].get_form(request)
        for campo in (
            "clabe",
            "pey_codi_status",
            "pey_bank_account_id",
            "pey_codi_status_actualizado_en",
            "cuenta_por_defecto",
        ):
            self.assertNotIn(campo, formulario.base_fields)

    def test_enlazar_exige_misma_clabe_y_version(self) -> None:
        cuenta = crear_cuenta(self.comercio, estado="pending", predeterminada=False)
        ident = cuenta.pey_bank_account_id
        cuenta.pey_bank_account_id = ""
        cuenta.registro_estado = "incierto"
        cuenta.save(update_fields=["pey_bank_account_id", "registro_estado"])
        with patch(
            "ambito.management.commands.enlazar_cuenta_pey.consultar_cuenta",
            return_value=CuentaPey(ident, "ACTIVE", "otra"),
        ):
            with self.assertRaises(CommandError):
                call_command("enlazar_cuenta_pey", cuenta=str(cuenta.pk), pey_id=ident)
        cuenta.refresh_from_db()
        self.assertEqual(cuenta.registro_estado, "incierto")

        def respuesta_tardia(identificador):
            CuentaCobro.objects.filter(pk=cuenta.pk).update(version=cuenta.version + 1)
            return CuentaPey(identificador, "ACTIVE", cuenta.clabe)

        with patch(
            "ambito.management.commands.enlazar_cuenta_pey.consultar_cuenta",
            side_effect=respuesta_tardia,
        ):
            with self.assertRaises(CommandError):
                call_command("enlazar_cuenta_pey", cuenta=str(cuenta.pk), pey_id=ident)
        cuenta.refresh_from_db()
        self.assertEqual(cuenta.registro_estado, "incierto")
        with patch(
            "ambito.management.commands.enlazar_cuenta_pey.consultar_cuenta",
            return_value=CuentaPey(ident, "ACTIVE", cuenta.clabe),
        ):
            call_command(
                "enlazar_cuenta_pey",
                cuenta=str(cuenta.pk),
                pey_id=ident,
                stdout=StringIO(),
            )
        cuenta.refresh_from_db()
        self.assertEqual(
            (cuenta.registro_estado, cuenta.pey_bank_account_id), ("registrado", ident)
        )
        self.assertEqual(cuenta.codi_status, "active")

    def test_enlazar_rechaza_uuid_invalido_sin_consultar(self) -> None:
        ident = "01J9ZQ4C8X7Y6W5V4T3S2R1Q0P"
        with patch(
            "ambito.management.commands.enlazar_cuenta_pey.consultar_cuenta"
        ) as consulta:
            with self.assertRaises(CommandError) as error:
                call_command("enlazar_cuenta_pey", cuenta="no-es-uuid", pey_id=ident)
        consulta.assert_not_called()
        self.assertNotIn(ident, str(error.exception))
        self.assertNotIn("no-es-uuid", str(error.exception))

    def test_enlazar_rechaza_id_duplicado_sin_exponer_datos(self) -> None:
        cuenta = crear_cuenta(self.comercio, estado="pending", predeterminada=False)
        cuenta.pey_bank_account_id = ""
        cuenta.registro_estado = "incierto"
        cuenta.save(update_fields=["pey_bank_account_id", "registro_estado"])
        otra = crear_cuenta(Comercio.objects.create(nombre="Otro"))
        ident = otra.pey_bank_account_id
        with patch(
            "ambito.management.commands.enlazar_cuenta_pey.consultar_cuenta",
            return_value=CuentaPey(ident, "ACTIVE", cuenta.clabe),
        ):
            with self.assertRaises(CommandError) as error:
                call_command("enlazar_cuenta_pey", cuenta=str(cuenta.pk), pey_id=ident)
        self.assertIn("ya asignado", str(error.exception))
        self.assertNotIn(ident, str(error.exception))
        self.assertNotIn(cuenta.clabe, str(error.exception))
        cuenta.refresh_from_db()
        self.assertEqual(cuenta.registro_estado, "incierto")
        self.assertEqual(cuenta.pey_bank_account_id, "")
        otra.refresh_from_db()
        self.assertEqual(otra.pey_bank_account_id, ident)
