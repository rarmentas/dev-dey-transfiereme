"""Contrato HTTP de cuenta. El transporte es falso: no hay red."""

from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from pey.cuentas import consultar_cuenta, registrar_cuenta
from pey.tipos import ErrorPey, ParametroInvalido

_LLAVE = "llave-prueba-no-imprimir"
_CLABE = "012180015826225713"
_BASE = "https://api.pey.mx"
_ULID = "01J9ZQ4C8X7Y6W5V4T3S2R1Q0P"


class _Transporte:
    def __init__(self, status: int, cuerpo: bytes) -> None:
        self.status = status
        self.cuerpo = cuerpo
        self.llamadas: list[tuple] = []

    def __call__(self, metodo, url, headers, cuerpo_bytes, timeout):
        self.llamadas.append((metodo, url, dict(headers), cuerpo_bytes, timeout))
        return self.status, self.cuerpo


def _error(tipo: str, request_id: str) -> bytes:
    return (
        '{"error": {"message": "fallo", "type": "'
        + tipo
        + '", "requestId": "'
        + request_id
        + '"}}'
    ).encode()


@override_settings(PEY_API_KEY=_LLAVE, PEY_BASE_URL=_BASE)
class CuentasHttpTests(SimpleTestCase):
    def setUp(self) -> None:
        self.red = patch("urllib.request.urlopen", side_effect=AssertionError("red"))
        self.red.start()
        self.addCleanup(self.red.stop)

    def test_registrar_envia_post_y_mapea_200(self) -> None:
        transporte = _Transporte(200, b'{"id": "01CUENTA", "codiStatus": "PENDING"}')
        cuenta = registrar_cuenta(
            alias="Tienda",
            nombre="Ana López",
            clabe=_CLABE,
            entidad="PERSON",
            transporte=transporte,
        )
        self.assertEqual(cuenta.id, "01CUENTA")
        self.assertEqual(cuenta.codi_status, "PENDING")
        metodo, url, headers, cuerpo, timeout = transporte.llamadas[0]
        self.assertEqual(metodo, "POST")
        self.assertEqual(url, f"{_BASE}/bank-account")
        self.assertEqual(headers["Authorization"], f"Bearer {_LLAVE}")
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(timeout, 10)
        self.assertEqual(
            cuerpo,
            b'{"alias": "Tienda", "name": "Ana L\xc3\xb3pez", "clabe": "'
            + _CLABE.encode()
            + b'", "entity": "PERSON"}',
        )
        self.assertNotIn(_LLAVE.encode(), cuerpo)

    def test_consultar_envia_get(self) -> None:
        transporte = _Transporte(
            200,
            (
                '{"id": "' + _ULID + '", "codiStatus": "ACTIVE", '
                '"clabe": "' + _CLABE + '", "errorMessage": ""}'
            ).encode(),
        )
        cuenta = consultar_cuenta(_ULID, transporte=transporte)
        self.assertEqual(cuenta.codi_status, "ACTIVE")
        self.assertEqual(cuenta.clabe, _CLABE)
        self.assertEqual(cuenta.error_message, "")
        metodo, url, headers, cuerpo, _timeout = transporte.llamadas[0]
        self.assertEqual(metodo, "GET")
        self.assertEqual(url, f"{_BASE}/bank-account/{_ULID}")
        self.assertEqual(cuerpo, b"")
        self.assertEqual(headers["Authorization"], f"Bearer {_LLAVE}")

    def test_400_y_404_traen_tipo_y_request_id(self) -> None:
        for status, tipo, request_id in (
            (400, "INVALID_CLABE", "req-400"),
            (404, "BANK_ACCOUNT_NOT_FOUND", "req-404"),
        ):
            with self.subTest(status=status):
                transporte = _Transporte(status, _error(tipo, request_id))
                with self.assertRaises(ErrorPey) as ctx:
                    consultar_cuenta(_ULID, transporte=transporte)
                self.assertEqual(ctx.exception.tipo, tipo)
                self.assertEqual(ctx.exception.request_id, request_id)

    def test_503_es_no_disponible(self) -> None:
        transporte = _Transporte(503, _error("UNAVAILABLE", "req-503"))
        with self.assertRaises(ErrorPey) as ctx:
            consultar_cuenta(_ULID, transporte=transporte)
        self.assertEqual(ctx.exception.tipo, "NO_DISPONIBLE")
        self.assertEqual(ctx.exception.request_id, "req-503")

    @override_settings(PEY_API_KEY="")
    def test_sin_llave_no_llama(self) -> None:
        transporte = _Transporte(200, b"{}")
        with self.assertRaises(ErrorPey) as ctx:
            registrar_cuenta(
                alias="Tienda",
                nombre="Ana",
                clabe=_CLABE,
                entidad="PERSON",
                transporte=transporte,
            )
        self.assertEqual(ctx.exception.tipo, "CONFIGURACION")
        self.assertEqual(transporte.llamadas, [])

    def test_clabe_invalida_no_llama(self) -> None:
        transporte = _Transporte(200, b"{}")
        with self.assertRaises(ParametroInvalido):
            registrar_cuenta(
                alias="Tienda",
                nombre="Ana",
                clabe="000",
                entidad="PERSON",
                transporte=transporte,
            )
        self.assertEqual(transporte.llamadas, [])

    def test_ulid_invalido_no_llama(self) -> None:
        transporte = _Transporte(200, b"{}")
        for identificador in ("01ABC", "01J9ZQ4C8X7Y6W5V4T3S2R1Q0I"):
            with self.subTest(identificador=identificador):
                with self.assertRaises(ParametroInvalido):
                    consultar_cuenta(identificador, transporte=transporte)
        self.assertEqual(transporte.llamadas, [])
