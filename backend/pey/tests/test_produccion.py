import json
from decimal import Decimal

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
        self.assertEqual(llamadas, [])

        with self.assertRaises(ErrorPey) as aviso:
            adaptador.crear_notificacion(monto=Decimal("1"), telefono="5512345678")
        self.assertEqual(aviso.exception.tipo, "CONFIGURACION")
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
            {"monto": Decimal("0.005")},
        ]
        for kwargs in qr_invalidos:
            with self.assertRaises(ParametroInvalido):
                adaptador.crear_qr(**kwargs)

        pn_invalidos = [
            {"monto": Decimal("0"), "telefono": "5512345678"},
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
            concepto="",
        )
        self.assertEqual(json.loads(vistos[0])["concept"], "Transferencia")
        self.assertEqual(json.loads(vistos[1])["concept"], "Transferencia")
        self.assertEqual(len(vistos), 2)
