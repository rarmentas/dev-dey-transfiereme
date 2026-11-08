"""Comandos de registro y diagnóstico. El transporte está parcheado: no hay red."""

from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from ambito.models import Comercio, Membresia

_CLABE = "012180015826225713"
_LLAVE = "SECRETO-LLAVE-NO-IMPRIMIR"
_WHSEC = "SECRETO-WHSEC-NO-IMPRIMIR"


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
        self.assertIn(_CLABE, texto)
        self.assertIn("PERSON", texto)
        self.assertNotIn(_LLAVE, texto)

    def test_confirmar_guarda_el_id(self) -> None:
        comercio = _vendedor("ana@ejemplo.mx")
        transporte = _Transporte(
            200,
            b'{"id": "01REG", "codiStatus": "ACTIVE"}',
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
        self.assertEqual(comercio.pey_bank_account_id, "01REG")
        self.assertEqual(comercio.pey_codi_status, Comercio.PeyCodiStatus.ACTIVE)

    @override_settings(DEBUG=True, PEY_ADAPTADOR="desarrollo", PEY_API_KEY="")
    def test_se_niega_en_desarrollo(self) -> None:
        _vendedor("ana@ejemplo.mx")
        transporte = _Transporte()
        with patch("pey.cuentas.transporte_urllib", transporte):
            with self.assertRaises(CommandError):
                call_command(
                    "registrar_cuenta_pey",
                    correo="ana@ejemplo.mx",
                    nombre="Ana",
                    entidad="PERSON",
                    confirmar=True,
                )
        self.assertEqual(transporte.llamadas, [])

    def test_diagnostico_no_imprime_secretos_y_sincroniza(self) -> None:
        comercio = _vendedor("ana@ejemplo.mx", pey_bank_account_id="01DIAG")
        transporte = _Transporte(
            200,
            b'{"id": "01DIAG", "codiStatus": "PROCESSING"}',
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
        self.assertIn("01DIAG", texto)
        self.assertIn("codiStatus: PROCESSING", texto)
        self.assertNotIn(_LLAVE, texto)
        self.assertNotIn(_WHSEC, texto)
        comercio.refresh_from_db()
        self.assertEqual(comercio.pey_codi_status, Comercio.PeyCodiStatus.PENDING)
        self.assertEqual(comercio.pey_bank_account_id, "01DIAG")
        self.assertTrue(transporte.llamadas)
        self.assertTrue(all(llamada[0] == "GET" for llamada in transporte.llamadas))
        self.assertNotIn(_LLAVE.encode(), transporte.llamadas[0][3])
