import email
import io
import json
from decimal import Decimal
from unittest.mock import patch
from urllib.parse import urlparse
from urllib.request import HTTPSHandler, build_opener
from urllib.response import addinfourl

from django.test import SimpleTestCase, override_settings

from pey.produccion import AdaptadorProduccion
from pey.tipos import ErrorPey, NotificacionCreada, ParametroInvalido, QrCreado

LLAVE = "llave-prueba"
QR_OK = b'{"id":"IDC-1","qrString":"qr-datos"}'
PN_OK = b'{"transactionId":"01ULID","codiId":"12345678901234567890"}'


class _Transporte:
    def __init__(self, status: int, cuerpo: bytes) -> None:
        self.status = status
        self.cuerpo = cuerpo
        self.llamadas: list[tuple] = []

    def __call__(self, metodo, url, headers, cuerpo_bytes, timeout):
        self.llamadas.append((metodo, url, headers, cuerpo_bytes, timeout))
        return self.status, self.cuerpo


def _adaptador(status: int, cuerpo: bytes) -> tuple[AdaptadorProduccion, _Transporte]:
    transporte = _Transporte(status, cuerpo)
    return AdaptadorProduccion(transporte=transporte), transporte


@override_settings(PEY_API_KEY=LLAVE, PEY_BASE_URL="https://api.pey.mx")
class ContratoProduccionTests(SimpleTestCase):
    def test_qr_envia_cuerpo_headers_y_url(self) -> None:
        adaptador, transporte = _adaptador(201, QR_OK)
        qr = adaptador.crear_qr(monto=Decimal("0.01"))

        self.assertEqual(qr, QrCreado(id="IDC-1", qr_string="qr-datos"))
        metodo, url, headers, cuerpo, timeout = transporte.llamadas[0]
        self.assertEqual(metodo, "POST")
        self.assertEqual(url, "https://api.pey.mx/codi/qr")
        self.assertEqual(
            headers,
            {
                "Authorization": "Bearer llave-prueba",
                "Content-Type": "application/json",
            },
        )
        self.assertEqual(timeout, 10)
        self.assertEqual(
            cuerpo,
            b'{"amount": 0.01, "concept": "Transferencia", "expiration": 0, "numRef": "0"}',
        )
        self.assertNotIn(b"0.010000", cuerpo)
        self.assertIsInstance(json.loads(cuerpo)["amount"], float)
        self.assertEqual(json.loads(cuerpo)["amount"], 0.01)

    def test_pn_envia_cuerpo_headers_y_url(self) -> None:
        adaptador, transporte = _adaptador(200, PN_OK)
        aviso = adaptador.crear_notificacion(
            monto=Decimal("0.01"),
            telefono="5512345678",
        )

        self.assertEqual(
            aviso,
            NotificacionCreada(
                transaction_id="01ULID",
                codi_id="12345678901234567890",
            ),
        )
        metodo, url, headers, cuerpo, timeout = transporte.llamadas[0]
        self.assertEqual(metodo, "POST")
        self.assertEqual(url, "https://api.pey.mx/codi/pn")
        self.assertEqual(headers["Authorization"], "Bearer llave-prueba")
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(timeout, 10)
        self.assertEqual(
            cuerpo,
            b'{"amount": 0.01, "phoneNumber": "5512345678", "concept": "Transferencia", "expiration": 360, "numRef": "0"}',
        )


_CUENTA = "01ARZ3NDEKTSV4RRFFQ69G5FAV"


@override_settings(PEY_API_KEY=LLAVE, PEY_BASE_URL="https://api.pey.mx")
class BankAccountIdProduccionTests(SimpleTestCase):
    def test_qr_con_cuenta_agrega_bank_account_id(self) -> None:
        adaptador, transporte = _adaptador(201, QR_OK)
        adaptador.crear_qr(monto=Decimal("0.01"), bank_account_id=_CUENTA)
        self.assertEqual(
            transporte.llamadas[0][3],
            b'{"amount": 0.01, "concept": "Transferencia", "expiration": 0, '
            b'"numRef": "0", "bankAccountId": "01ARZ3NDEKTSV4RRFFQ69G5FAV"}',
        )

    def test_pn_con_cuenta_agrega_bank_account_id(self) -> None:
        adaptador, transporte = _adaptador(200, PN_OK)
        adaptador.crear_notificacion(
            monto=Decimal("0.01"),
            telefono="5512345678",
            bank_account_id=_CUENTA,
        )
        self.assertEqual(
            transporte.llamadas[0][3],
            b'{"amount": 0.01, "phoneNumber": "5512345678", "concept": "Transferencia", '
            b'"expiration": 360, "numRef": "0", "bankAccountId": "01ARZ3NDEKTSV4RRFFQ69G5FAV"}',
        )

    def test_ulid_invalido_no_llama_al_transporte(self) -> None:
        adaptador, transporte = _adaptador(201, QR_OK)
        with self.assertRaises(ParametroInvalido):
            adaptador.crear_qr(monto=Decimal("0.01"), bank_account_id="no-es-ulid")
        with self.assertRaises(ParametroInvalido):
            adaptador.crear_notificacion(
                monto=Decimal("0.01"),
                telefono="5512345678",
                bank_account_id="01arz3ndektsv4rrffq69g5fav",
            )
        self.assertEqual(transporte.llamadas, [])

    def test_concepto_explicito_se_conserva_y_el_vacio_no(self) -> None:
        adaptador, transporte = _adaptador(201, QR_OK)
        adaptador.crear_qr(monto=Decimal("10.50"), concepto="Tacos", num_ref="42")
        concepto = json.loads(transporte.llamadas[0][3])["concept"]
        self.assertEqual(concepto, "Tacos")
        self.assertIn(b'"amount": 10.50', transporte.llamadas[0][3])

    def test_limites_de_monto_validos(self) -> None:
        qr, transporte_qr = _adaptador(201, QR_OK)
        qr.crear_qr(monto=Decimal("0"))
        self.assertIn(b'"amount": 0.00', transporte_qr.llamadas[0][3])

        pn, transporte_pn = _adaptador(200, PN_OK)
        pn.crear_notificacion(monto=Decimal("1000000"), telefono="5512345678")
        self.assertIn(b'"amount": 1000000.00', transporte_pn.llamadas[0][3])


@override_settings(PEY_API_KEY=LLAVE)
class ErroresProduccionTests(SimpleTestCase):
    def test_400_copia_el_error_de_pey_y_loguea_el_request_id(self) -> None:
        cuerpo = json.dumps(
            {
                "error": {
                    "message": "El monto no es válido",
                    "type": "INVALID_AMOUNT",
                    "requestId": "req_abc",
                }
            }
        ).encode()
        adaptador, _transporte = _adaptador(400, cuerpo)

        with self.assertLogs("pey.produccion", level="WARNING") as logs:
            with self.assertRaises(ErrorPey) as ctx:
                adaptador.crear_qr(monto=Decimal("1.00"))

        self.assertEqual(ctx.exception.tipo, "INVALID_AMOUNT")
        self.assertEqual(ctx.exception.mensaje, "El monto no es válido")
        self.assertEqual(ctx.exception.request_id, "req_abc")
        self.assertFalse(ctx.exception.puede_haberse_creado)
        texto = "\n".join(logs.output)
        self.assertIn("req_abc", texto)
        self.assertNotIn(LLAVE, texto)
        self.assertNotIn("Authorization", texto)
        self.assertNotIn("Bearer", texto)

    def test_5xx_es_no_disponible(self) -> None:
        for status in (500, 503):
            adaptador, transporte = _adaptador(status, b"")
            with self.assertLogs("pey.produccion", level="WARNING") as logs:
                with self.assertRaises(ErrorPey) as ctx:
                    adaptador.crear_notificacion(
                        monto=Decimal("10"),
                        telefono="5512345678",
                    )
            self.assertEqual(ctx.exception.tipo, "NO_DISPONIBLE")
            self.assertTrue(ctx.exception.puede_haberse_creado)
            self.assertEqual(len(transporte.llamadas), 1)
            self.assertNotIn(LLAVE, "\n".join(logs.output))

    def test_excepcion_de_red_es_no_disponible(self) -> None:
        def transporte(*args, **kwargs):
            raise TimeoutError("tardó")

        adaptador = AdaptadorProduccion(transporte=transporte)
        with self.assertLogs("pey.produccion", level="WARNING") as logs:
            with self.assertRaises(ErrorPey) as ctx:
                adaptador.crear_qr(monto=Decimal("1"))
        self.assertEqual(ctx.exception.tipo, "NO_DISPONIBLE")
        self.assertTrue(ctx.exception.puede_haberse_creado)
        texto = "\n".join(logs.output)
        self.assertIn("TimeoutError", texto)
        self.assertNotIn(LLAVE, texto)
        self.assertNotIn("Authorization", texto)

    def test_json_roto_o_incompleto_es_respuesta_invalida(self) -> None:
        for cuerpo in (b"{roto", b'{"id":"solo"}', b"[]"):
            adaptador, _transporte = _adaptador(201, cuerpo)
            with self.assertRaises(ErrorPey) as ctx:
                adaptador.crear_qr(monto=Decimal("1"))
            self.assertEqual(ctx.exception.tipo, "RESPUESTA_INVALIDA")
            self.assertTrue(ctx.exception.puede_haberse_creado)

    def test_400_ilegible_no_pudo_crearse(self) -> None:
        adaptador, _transporte = _adaptador(400, b"no-json")
        with self.assertRaises(ErrorPey) as ctx:
            adaptador.crear_qr(monto=Decimal("1"))
        self.assertEqual(ctx.exception.tipo, "RESPUESTA_INVALIDA")
        self.assertFalse(ctx.exception.puede_haberse_creado)

    def test_estado_inesperado_loguea_request_id_y_pudo_crearse(self) -> None:
        cuerpo = json.dumps(
            {
                "error": {
                    "message": "no",
                    "type": "NO",
                    "requestId": "req_estado",
                }
            }
        ).encode()
        for status in (301, 302, 401, 403, 429):
            adaptador, transporte = _adaptador(status, cuerpo)
            with self.assertLogs("pey.produccion", level="WARNING") as logs:
                with self.assertRaises(ErrorPey) as ctx:
                    adaptador.crear_qr(monto=Decimal("1"))
            self.assertEqual(ctx.exception.tipo, "RESPUESTA_INVALIDA")
            self.assertEqual(ctx.exception.request_id, "req_estado")
            self.assertTrue(ctx.exception.puede_haberse_creado)
            self.assertEqual(len(transporte.llamadas), 1)
            texto = "\n".join(logs.output)
            self.assertIn("req_estado", texto)
            self.assertNotIn(LLAVE, texto)
            self.assertNotIn("Authorization", texto)
            self.assertNotIn("Bearer", texto)


class SinLlaveTests(SimpleTestCase):
    @override_settings(PEY_API_KEY="")
    def test_no_llama_al_transporte(self) -> None:
        llamadas = []

        def transporte(*args, **kwargs):
            llamadas.append(args)
            raise AssertionError("no debe llamar")

        adaptador = AdaptadorProduccion(transporte=transporte)
        with self.assertRaises(ErrorPey) as ctx:
            adaptador.crear_qr(monto=Decimal("1"))
        self.assertEqual(ctx.exception.tipo, "CONFIGURACION")
        self.assertFalse(ctx.exception.puede_haberse_creado)
        self.assertEqual(llamadas, [])

        with self.assertRaises(ErrorPey) as aviso:
            adaptador.crear_notificacion(monto=Decimal("1"), telefono="5512345678")
        self.assertEqual(aviso.exception.tipo, "CONFIGURACION")
        self.assertFalse(aviso.exception.puede_haberse_creado)
        self.assertEqual(llamadas, [])


@override_settings(PEY_API_KEY=LLAVE)
class ValidacionCompartidaTests(SimpleTestCase):
    def test_rechaza_sin_llamar_al_transporte(self) -> None:
        llamadas = []

        def transporte(*args, **kwargs):
            llamadas.append(args)
            raise AssertionError("no debe llamar")

        adaptador = AdaptadorProduccion(transporte=transporte)
        qr_invalidos = [
            {"monto": Decimal("10"), "num_ref": "12A"},
            {"monto": Decimal("10"), "num_ref": "12345678"},
            {"monto": Decimal("10"), "expiracion_s": 100},
            {"monto": Decimal("-0.01")},
            {"monto": Decimal("-0.00")},
            {"monto": Decimal("0.005")},
            {"monto": Decimal("10.500")},
            {"monto": Decimal("1e27")},
            {"monto": Decimal("12345678901234567890123456.789")},
            {"monto": Decimal("10000000000")},
        ]
        for kwargs in qr_invalidos:
            with self.assertRaises(ParametroInvalido):
                adaptador.crear_qr(**kwargs)

        pn_invalidos = [
            {"monto": Decimal("0"), "telefono": "5512345678"},
            {"monto": Decimal("-0.00"), "telefono": "5512345678"},
            {"monto": Decimal("0.005"), "telefono": "5512345678"},
            {"monto": Decimal("1e27"), "telefono": "5512345678"},
            {"monto": Decimal("12345678901234567890123456.789"), "telefono": "5512345678"},
            {"monto": Decimal("1000000.01"), "telefono": "5512345678"},
            {"monto": Decimal("10"), "telefono": "551234567"},
            {"monto": Decimal("10"), "telefono": "5512345678", "expiracion_s": 100},
            {"monto": Decimal("10"), "telefono": "5512345678", "num_ref": "12A"},
        ]
        for kwargs in pn_invalidos:
            with self.assertRaises(ParametroInvalido):
                adaptador.crear_notificacion(**kwargs)

        self.assertEqual(llamadas, [])

    def test_concepto_vacio_se_envia_como_transferencia(self) -> None:
        vistos = []

        def transporte(metodo, url, headers, cuerpo_bytes, timeout):
            vistos.append(cuerpo_bytes)
            if url.endswith("/codi/qr"):
                return 201, QR_OK
            return 200, PN_OK

        adaptador = AdaptadorProduccion(transporte=transporte)
        adaptador.crear_qr(monto=Decimal("8"), concepto="")
        adaptador.crear_notificacion(
            monto=Decimal("8"),
            telefono="5512345678",
            concepto="   ",
        )
        self.assertEqual(json.loads(vistos[0])["concept"], "Transferencia")
        self.assertEqual(json.loads(vistos[1])["concept"], "Transferencia")
        self.assertEqual(len(vistos), 2)

    def test_uno_diez_sale_sin_redondear(self) -> None:
        adaptador, transporte = _adaptador(201, QR_OK)
        adaptador.crear_qr(monto=Decimal("1.10"))
        self.assertIn(b'"amount": 1.10', transporte.llamadas[0][3])


class _HostUnico(HTTPSHandler):
    def __init__(self, llamadas: list[tuple[str, str | None]]) -> None:
        super().__init__()
        self._llamadas = llamadas

    def https_open(self, req):
        self._llamadas.append((req.full_url, req.get_header("Authorization")))
        if len(self._llamadas) > 1:
            cuerpo = io.BytesIO(b"ok")
            headers = email.message_from_string("")
            respuesta = addinfourl(cuerpo, headers, req.full_url, 200)
            respuesta.msg = "OK"
            return respuesta
        cuerpo = io.BytesIO(
            b'{"error":{"message":"redir","type":"NO","requestId":"req_redir"}}'
        )
        headers = email.message_from_string("Location: https://evil.example/robo\n")
        respuesta = addinfourl(cuerpo, headers, req.full_url, 302)
        respuesta.msg = "Found"
        return respuesta


@override_settings(PEY_API_KEY=LLAVE, PEY_BASE_URL="https://api.pey.mx")
class RedireccionTests(SimpleTestCase):
    def test_un_302_no_reenvia_el_bearer_a_otro_host(self) -> None:
        llamadas: list[tuple[str, str | None]] = []

        def _build(*handlers):
            return build_opener(_HostUnico(llamadas), *handlers)

        adaptador = AdaptadorProduccion()
        with (
            patch("pey.produccion.build_opener", _build),
            self.assertLogs("pey.produccion", level="WARNING") as logs,
        ):
            with self.assertRaises(ErrorPey) as ctx:
                adaptador.crear_qr(monto=Decimal("1"))

        self.assertEqual(ctx.exception.tipo, "RESPUESTA_INVALIDA")
        self.assertTrue(ctx.exception.puede_haberse_creado)
        self.assertEqual(ctx.exception.request_id, "req_redir")
        self.assertIn("no debe reintentar", ErrorPey.__doc__)
        self.assertEqual(len(llamadas), 1)
        url, autorizacion = llamadas[0]
        self.assertEqual(urlparse(url).netloc, "api.pey.mx")
        self.assertEqual(autorizacion, "Bearer llave-prueba")
        self.assertTrue(
            all(urlparse(destino).netloc == "api.pey.mx" for destino, _auth in llamadas)
        )
        texto = "\n".join(logs.output)
        self.assertIn("req_redir", texto)
        self.assertNotIn(LLAVE, texto)
        self.assertNotIn("evil.example", texto)
