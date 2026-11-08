"""Comandos de registro y diagnóstico. El transporte está parcheado: no hay red."""

from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from ambito.models import Comercio, Membresia

_CLABE = "012180015826225713"
_MASCARA = "**************5713"
_LLAVE = "SECRETO-LLAVE-NO-IMPRIMIR"
_WHSEC = "SECRETO-WHSEC-NO-IMPRIMIR"
_ULID = "01J9ZQ4C8X7Y6W5V4T3S2R1Q0P"
_ULID_NUEVO = "01J9ZQ4C8X7Y6W5V4T3S2R1Q0M"


class _Transporte:
    def __init__(self, status: int = 200, cuerpo: bytes = b"") -> None:
        self.status = status
        self.cuerpo = cuerpo
        self.llamadas: list[tuple] = []

    def __call__(self, metodo, url, headers, cuerpo_bytes, timeout):
        self.llamadas.append((metodo, url, headers, cuerpo_bytes, timeout))
        return self.status, self.cuerpo


def _vendedor(correo: str, **comercio) -> Comercio:
    datos = {"nombre": "Tienda", "clabe": _CLABE}
    datos.update(comercio)
    local = Comercio.objects.create(**datos)
    usuario = User.objects.create_user(username=correo, email=correo, password="pass")
    Membresia.objects.create(usuario=usuario, comercio=local)
    return local


@override_settings(
    DEBUG=True,
    PEY_ADAPTADOR="produccion",
    PEY_API_KEY=_LLAVE,
    PEY_WEBHOOK_SECRET=_WHSEC,
    PEY_BASE_URL="https://api.pey.mx",
    WEBHOOK_BASE_URL="https://ejemplo.mx",
)
class ComandosPeyTests(TestCase):
    def setUp(self) -> None:
        self.red = patch("urllib.request.urlopen", side_effect=AssertionError("red"))
        self.red.start()
        self.addCleanup(self.red.stop)

    def test_sin_confirmar_no_llama(self) -> None:
        _vendedor("ana@ejemplo.mx")
        transporte = _Transporte()
        salida = StringIO()
        with patch("pey.cuentas.transporte_urllib", transporte):
            call_command(
                "registrar_cuenta_pey",
                correo="ana@ejemplo.mx",
                nombre="Ana López",
                entidad="PERSON",
                stdout=salida,
            )
        self.assertEqual(transporte.llamadas, [])
        texto = salida.getvalue()
        self.assertIn("Sin --confirmar no se llama a pey.", texto)
        self.assertIn(_MASCARA, texto)
        self.assertNotIn(_CLABE, texto)
        self.assertIn("PERSON", texto)
        self.assertNotIn(_LLAVE, texto)

    def test_confirmar_guarda_el_id(self) -> None:
        comercio = _vendedor("ana@ejemplo.mx")
        transporte = _Transporte(
            200,
            ('{"id": "' + _ULID_NUEVO + '", "codiStatus": "ACTIVE"}').encode(),
        )
        with patch("pey.cuentas.transporte_urllib", transporte):
            call_command(
                "registrar_cuenta_pey",
                correo="ana@ejemplo.mx",
                nombre="Ana",
                entidad="BUSINESS",
                alias="Tienda",
                confirmar=True,
            )
        self.assertEqual(len(transporte.llamadas), 1)
        self.assertEqual(transporte.llamadas[0][0], "POST")
        comercio.refresh_from_db()
        self.assertEqual(comercio.pey_bank_account_id, _ULID_NUEVO)
        self.assertEqual(comercio.pey_codi_status, Comercio.PeyCodiStatus.ACTIVE)

    @override_settings(DEBUG=True, PEY_ADAPTADOR="desarrollo", PEY_API_KEY="")
    def test_se_niega_en_desarrollo(self) -> None:
        _vendedor("ana@ejemplo.mx")
        transporte = _Transporte()
        with patch("pey.cuentas.transporte_urllib", transporte):
            with self.assertRaises(CommandError) as ctx:
                call_command(
                    "registrar_cuenta_pey",
                    correo="ana@ejemplo.mx",
                    nombre="Ana",
                    entidad="PERSON",
                    confirmar=True,
                )
        self.assertEqual(transporte.llamadas, [])
        self.assertIn(
            "Este comando solo corre con PEY_ADAPTADOR=produccion.",
            str(ctx.exception),
        )

    def test_confirmar_imprime_codi_status_crudo_de_pey(self) -> None:
        comercio = _vendedor("ana@ejemplo.mx")
        transporte = _Transporte(
            200,
            ('{"id": "' + _ULID_NUEVO + '", "codiStatus": "PROCESSING"}').encode(),
        )
        salida = StringIO()
        with patch("pey.cuentas.transporte_urllib", transporte):
            call_command(
                "registrar_cuenta_pey",
                correo="ana@ejemplo.mx",
                nombre="Ana",
                entidad="BUSINESS",
                confirmar=True,
                stdout=salida,
            )
        self.assertIn("codiStatus=PROCESSING", salida.getvalue())
        comercio.refresh_from_db()
        self.assertEqual(comercio.pey_codi_status, Comercio.PeyCodiStatus.PENDING)
        self.assertEqual(comercio.pey_bank_account_id, _ULID_NUEVO)

    def test_diagnostico_no_imprime_secretos_y_sincroniza(self) -> None:
        comercio = _vendedor("ana@ejemplo.mx", pey_bank_account_id=_ULID)
        transporte = _Transporte(
            200,
            ('{"id": "' + _ULID + '", "codiStatus": "PROCESSING", "clabe": "' + _CLABE + '"}').encode(),
        )
        salida = StringIO()
        with patch("pey.cuentas.transporte_urllib", transporte):
            call_command(
                "diagnostico_pey",
                correo="ana@ejemplo.mx",
                stdout=salida,
            )
        texto = salida.getvalue()
        self.assertIn("modo: produccion", texto)
        self.assertIn("PEY_API_KEY: sí", texto)
        self.assertIn("PEY_WEBHOOK_SECRET: sí", texto)
        self.assertIn("https://ejemplo.mx/api/webhooks/pey/", texto)
        self.assertIn(_ULID, texto)
        self.assertIn(_MASCARA, texto)
        self.assertNotIn(_CLABE, texto)
        self.assertIn("codiStatus: pending", texto)
        self.assertNotIn(_LLAVE, texto)
        self.assertNotIn(_WHSEC, texto)
        comercio.refresh_from_db()
        self.assertEqual(comercio.pey_codi_status, Comercio.PeyCodiStatus.PENDING)
        self.assertEqual(comercio.pey_bank_account_id, _ULID)
        self.assertEqual(len(transporte.llamadas), 1)
        self.assertEqual(transporte.llamadas[0][0], "GET")
        self.assertNotIn(_LLAVE.encode(), transporte.llamadas[0][3])

    def test_registro_repetido_exige_reemplazar_y_no_imprime_la_clabe(self) -> None:
        _vendedor("ana@ejemplo.mx", pey_bank_account_id=_ULID)
        transporte = _Transporte()
        salida = StringIO()
        error = StringIO()
        with patch("pey.cuentas.transporte_urllib", transporte):
            with self.assertRaises(CommandError) as ctx:
                call_command(
                    "registrar_cuenta_pey",
                    correo="ana@ejemplo.mx",
                    nombre="Ana",
                    entidad="PERSON",
                    confirmar=True,
                    stdout=salida,
                    stderr=error,
                )
        self.assertEqual(transporte.llamadas, [])
        texto = salida.getvalue() + error.getvalue() + str(ctx.exception)
        self.assertNotIn(_CLABE, texto)
        self.assertIn("--reemplazar", str(ctx.exception))

    def test_diagnostico_imprime_el_fallo_sin_cambiar_el_estado(self) -> None:
        comercio = _vendedor(
            "ana@ejemplo.mx",
            pey_bank_account_id=_ULID,
            pey_codi_status=Comercio.PeyCodiStatus.ACTIVE,
        )
        transporte = _Transporte(503, b'{"error":{"message":"caido","type":"UNAVAILABLE","requestId":"req-503"}}')
        salida = StringIO()
        with patch("pey.cuentas.transporte_urllib", transporte):
            call_command("diagnostico_pey", correo="ana@ejemplo.mx", stdout=salida)
        texto = salida.getvalue()
        self.assertIn("tipo=NO_DISPONIBLE", texto)
        self.assertIn("request_id=req-503", texto)
        self.assertNotIn(_CLABE, texto)
        self.assertNotIn(_LLAVE, texto)
        comercio.refresh_from_db()
        self.assertEqual(comercio.pey_codi_status, Comercio.PeyCodiStatus.ACTIVE)
        self.assertEqual(comercio.pey_bank_account_id, _ULID)
        self.assertEqual(len(transporte.llamadas), 1)
