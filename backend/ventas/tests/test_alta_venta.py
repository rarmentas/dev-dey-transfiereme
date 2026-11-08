"""Alta de venta. El puerto es el adaptador de desarrollo o un doble: sin red."""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from ambito.models import Comercio, Membresia
from movimientos.models import Cobro, Movimiento
from pey.desarrollo import AdaptadorDesarrollo
from pey.tipos import ErrorPey, ParametroInvalido, QrCreado
from sesion.middleware import _MENSAJE_SIN_SESION
from ventas.servicio import (
    ConceptoInvalido,
    MontoInvalido,
    ReferenciaInvalida,
    crear_venta_qr,
)

_RUTA = "/api/ventas/"


class _DoblePuerto:
    """Cuenta llamadas. No crea QR ni habla con pey."""

    def __init__(self) -> None:
        self.llamadas: list[tuple] = []

    def cuenta_active(self, comercio: Comercio) -> bool:
        self.llamadas.append(("cuenta_active", comercio.pk))
        return True

    def crear_qr(self, **kwargs) -> QrCreado:
        self.llamadas.append(("crear_qr", kwargs))
        return QrCreado(id="no-deberia", qr_string="no-deberia")


class _Espia(AdaptadorDesarrollo):
    def __init__(self, fallar_con: ErrorPey | None = None) -> None:
        super().__init__(fallar_con=fallar_con)
        self.qr_kwargs: list[dict] = []
        self.qr: QrCreado | None = None

    def crear_qr(self, **kwargs) -> QrCreado:
        self.qr_kwargs.append(kwargs)
        self.qr = super().crear_qr(**kwargs)
        return self.qr


class _PuertoParametroInvalido:
    def cuenta_active(self, comercio: Comercio) -> bool:
        return True

    def crear_qr(self, **kwargs) -> QrCreado:
        raise ParametroInvalido("num_ref debe ser de 1 a 7 dígitos")


class AltaVentaApiTests(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.comercio_a = Comercio.objects.create(
            nombre="Comercio A",
            semilla_active_dev=True,
        )
        self.comercio_b = Comercio.objects.create(
            nombre="Comercio B",
            semilla_active_dev=True,
        )
        self.comercio_off = Comercio.objects.create(
            nombre="Sin cuenta",
            semilla_active_dev=False,
        )
        self.usuario_a = User.objects.create_user(username="vendedor_a", password="pass-a")
        self.usuario_b = User.objects.create_user(username="vendedor_b", password="pass-b")
        self.usuario_off = User.objects.create_user(
            username="vendedor_off",
            password="pass-off",
        )
        Membresia.objects.create(usuario=self.usuario_a, comercio=self.comercio_a)
        Membresia.objects.create(usuario=self.usuario_b, comercio=self.comercio_b)
        Membresia.objects.create(usuario=self.usuario_off, comercio=self.comercio_off)

    def _entrar(self, usuario: User) -> None:
        self.client.force_login(usuario)

    def test_referencia_invalida_no_llama_al_adaptador(self) -> None:
        self._entrar(self.usuario_a)
        doble = _DoblePuerto()
        for referencia in ("12A", "12345678", "   "):
            with self.subTest(referencia=referencia):
                with patch("ventas.servicio.obtener_puerto", return_value=doble):
                    respuesta = self.client.post(
                        _RUTA,
                        {"monto": "0.01", "concepto": "Taco", "referencia": referencia},
                        format="json",
                    )
                self.assertEqual(respuesta.status_code, 400)
                self.assertIn("referencia", respuesta.json())
                with self.assertRaises(ReferenciaInvalida):
                    crear_venta_qr(
                        comercio=self.comercio_a,
                        monto=Decimal("0.01"),
                        concepto="Taco",
                        referencia=referencia,
                        puerto=doble,
                    )
                self.assertEqual(doble.llamadas, [])
        self.assertEqual(Cobro.objects.count(), 0)
        self.assertEqual(Movimiento.objects.count(), 0)

    def test_concepto_vacio_se_envia_como_transferencia(self) -> None:
        self._entrar(self.usuario_a)
        cuerpos = (
            {"monto": "0.01", "concepto": ""},
            {"monto": "0.01", "concepto": "   "},
            {"monto": "0.01"},
        )
        for cuerpo in cuerpos:
            with self.subTest(cuerpo=cuerpo):
                espia = _Espia()
                with patch("ventas.servicio.obtener_puerto", return_value=espia):
                    respuesta = self.client.post(_RUTA, cuerpo, format="json")
                self.assertEqual(respuesta.status_code, 201)
                self.assertEqual(len(espia.qr_kwargs), 1)
                self.assertEqual(espia.qr_kwargs[0]["concepto"], "Transferencia")
                self.assertEqual(espia.qr_kwargs[0]["monto"], Decimal("0.01"))
                self.assertEqual(espia.qr_kwargs[0]["num_ref"], "0")
                self.assertEqual(espia.qr_kwargs[0]["expiracion_s"], 600)
                cuerpo_json = respuesta.json()
                self.assertEqual(cuerpo_json["concepto"], "Transferencia")
                self.assertEqual(cuerpo_json["monto"], "0.01")
                movimiento = Movimiento.objects.get(pk=cuerpo_json["movimiento_id"])
                self.assertIsInstance(movimiento.monto, Decimal)
                self.assertEqual(movimiento.monto, Decimal("0.01"))
                self.assertEqual(movimiento.concepto, "Transferencia")
                self.assertEqual(movimiento.concepto_visible, "Transferencia")

    def test_error_pey_no_persiste_ni_deja_pagado(self) -> None:
        self._entrar(self.usuario_a)
        for puede in (False, True):
            with self.subTest(puede_haberse_creado=puede):
                adaptador = AdaptadorDesarrollo(
                    fallar_con=ErrorPey(
                        "INVALID_STATE",
                        "rechazado-por-pey",
                        "req-1",
                        puede_haberse_creado=puede,
                    )
                )
                with patch("ventas.servicio.obtener_puerto", return_value=adaptador):
                    with self.assertLogs("ventas.views", level="WARNING") as logs:
                        respuesta = self.client.post(
                            _RUTA,
                            {"monto": "0.01", "concepto": "Taco"},
                            format="json",
                        )
                self.assertEqual(respuesta.status_code, 502)
                self.assertEqual(
                    respuesta.json(),
                    {
                        "detail": "pey no pudo crear el cobro.",
                        "tipo": "INVALID_STATE",
                        "request_id": "req-1",
                        "puede_haberse_creado": puede,
                    },
                )
                texto = " ".join(logs.output)
                self.assertIn("INVALID_STATE", texto)
                self.assertIn("req-1", texto)
                self.assertIn(f"comercio_id={self.comercio_a.pk}", texto)
                self.assertNotIn("rechazado-por-pey", texto)
                self.assertNotIn("PEY_API_KEY", texto)
                self.assertEqual(Cobro.objects.count(), 0)
                self.assertEqual(Movimiento.objects.count(), 0)
                self.assertFalse(
                    Movimiento.objects.filter(estado=Movimiento.Estado.PAGADO).exists()
                )

    def test_exito_crea_cobro_qr_venta_y_movimiento_pendiente(self) -> None:
        self._entrar(self.usuario_a)
        espia = _Espia()
        antes = timezone.now()
        with patch("ventas.servicio.obtener_puerto", return_value=espia):
            respuesta = self.client.post(
                _RUTA,
                {"monto": "0.01", "concepto": "Tacos", "referencia": "42"},
                format="json",
            )
        despues = timezone.now()
        self.assertEqual(respuesta.status_code, 201)
        cuerpo = respuesta.json()
        self.assertIsNotNone(espia.qr)
        cobro = Cobro.objects.get(pk=cuerpo["cobro_id"])
        movimiento = Movimiento.objects.get(pk=cuerpo["movimiento_id"])
        self.assertEqual(espia.qr_kwargs[0]["expiracion_s"], 600)
        self.assertEqual(espia.qr_kwargs[0]["num_ref"], "42")
        self.assertEqual(espia.qr_kwargs[0]["concepto"], "Tacos")
        self.assertEqual(espia.qr_kwargs[0]["monto"], Decimal("0.01"))
        self.assertEqual(cobro.pey_qr_id, espia.qr.id)
        self.assertEqual(cobro.canal, Movimiento.Canal.QR_VENTA)
        self.assertEqual(cobro.comercio_id, self.comercio_a.pk)
        self.assertEqual(cobro.monto, Decimal("0.01"))
        self.assertEqual(cobro.concepto, "Tacos")
        self.assertGreaterEqual(cobro.vence_en, antes + timedelta(seconds=600))
        self.assertLessEqual(cobro.vence_en, despues + timedelta(seconds=600))
        self.assertEqual(movimiento.cobro_id, cobro.pk)
        self.assertEqual(movimiento.comercio_id, self.comercio_a.pk)
        self.assertEqual(movimiento.estado, Movimiento.Estado.PENDIENTE)
        self.assertEqual(movimiento.origen, Movimiento.Origen.ORIGEN_DESARROLLO)
        self.assertEqual(movimiento.canal, Movimiento.Canal.QR_VENTA)
        self.assertEqual(
            cuerpo,
            {
                "movimiento_id": movimiento.pk,
                "cobro_id": cobro.pk,
                "canal": "qr_venta",
                "monto": "0.01",
                "concepto": "Tacos",
                "estado": "pendiente",
                "vence_en": cobro.vence_en.isoformat(),
                "qr_string": espia.qr.qr_string,
                "origen": "origen_desarrollo",
            },
        )
        self.assertFalse(
            Movimiento.objects.filter(estado=Movimiento.Estado.PAGADO).exists()
        )

    @override_settings(DEBUG=True, PEY_ADAPTADOR="desarrollo", PEY_API_KEY="")
    def test_exito_con_puerto_de_desarrollo_por_settings(self) -> None:
        self._entrar(self.usuario_a)
        respuesta = self.client.post(
            _RUTA,
            {"monto": "1.50", "concepto": "Demo"},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 201)
        cuerpo = respuesta.json()
        self.assertEqual(cuerpo["origen"], "origen_desarrollo")
        self.assertTrue(cuerpo["qr_string"].startswith("cody-dev://qr/dev-qr-"))
        cobro = Cobro.objects.get(pk=cuerpo["cobro_id"])
        self.assertEqual(cobro.comercio_id, self.comercio_a.pk)
        self.assertEqual(cobro.pey_qr_id, cuerpo["qr_string"].removeprefix("cody-dev://qr/"))
        self.assertEqual(
            Movimiento.objects.get(pk=cuerpo["movimiento_id"]).origen,
            Movimiento.Origen.ORIGEN_DESARROLLO,
        )

    def test_cuenta_no_active_no_llama_crear_qr(self) -> None:
        self._entrar(self.usuario_off)
        adaptador = AdaptadorDesarrollo()
        with patch.object(adaptador, "crear_qr", wraps=adaptador.crear_qr) as crear_qr:
            with patch("ventas.servicio.obtener_puerto", return_value=adaptador):
                respuesta = self.client.post(
                    _RUTA,
                    {"monto": "0.01", "concepto": "Taco"},
                    format="json",
                )
        self.assertEqual(respuesta.status_code, 409)
        self.assertEqual(respuesta.json(), {"detail": "La cuenta no está ACTIVE."})
        self.assertEqual(crear_qr.call_count, 0)
        self.assertEqual(Cobro.objects.count(), 0)
        self.assertEqual(Movimiento.objects.count(), 0)

    def test_sin_sesion_comercio_en_cuerpo_y_montos_invalidos(self) -> None:
        respuesta = self.client.post(
            _RUTA,
            {"monto": "0.01"},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(respuesta.json()["detail"], _MENSAJE_SIN_SESION)

        self._entrar(self.usuario_a)
        for cuerpo in (
            {"monto": "0.01", "comercio": self.comercio_b.pk},
            {"monto": "0.01", "comercio_id": self.comercio_b.pk},
        ):
            with self.subTest(cuerpo=cuerpo):
                respuesta = self.client.post(_RUTA, cuerpo, format="json")
                self.assertEqual(respuesta.status_code, 400)
                self.assertIn("comercio", respuesta.json()["detail"].lower())

        doble = _DoblePuerto()
        invalidos = ("0", "-1", "0.005", "abc", 0, -5, "10000000000")
        for monto in invalidos:
            with self.subTest(monto=monto):
                with patch("ventas.servicio.obtener_puerto", return_value=doble):
                    respuesta = self.client.post(
                        _RUTA,
                        {"monto": monto, "referencia": "1"},
                        format="json",
                    )
                self.assertEqual(respuesta.status_code, 400)
                self.assertIn("monto", respuesta.json())
        for monto in (Decimal("0"), Decimal("-1"), Decimal("0.005")):
            with self.subTest(servicio=monto):
                with self.assertRaises(MontoInvalido):
                    crear_venta_qr(
                        comercio=self.comercio_a,
                        monto=monto,
                        concepto="Taco",
                        referencia="1",
                        puerto=doble,
                    )
        self.assertEqual(doble.llamadas, [])
        self.assertEqual(Cobro.objects.count(), 0)
        self.assertEqual(Movimiento.objects.count(), 0)

    def test_sin_membresia_responde_403(self) -> None:
        usuario = User.objects.create_user(username="sin_comercio", password="pass")
        self._entrar(usuario)
        respuesta = self.client.post(_RUTA, {"monto": "0.01"}, format="json")
        self.assertEqual(respuesta.status_code, 403)
        self.assertIn("comercio", respuesta.json()["detail"].lower())
        self.assertEqual(Cobro.objects.count(), 0)

    def test_concepto_demasiado_largo_no_llama_al_adaptador(self) -> None:
        self._entrar(self.usuario_a)
        doble = _DoblePuerto()
        with patch("ventas.servicio.obtener_puerto", return_value=doble):
            respuesta = self.client.post(
                _RUTA,
                {"monto": "0.01", "concepto": "a" * 501},
                format="json",
            )
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("concepto", respuesta.json())
        with self.assertRaises(ConceptoInvalido):
            crear_venta_qr(
                comercio=self.comercio_a,
                monto=Decimal("0.01"),
                concepto="a" * 501,
                referencia="1",
                puerto=doble,
            )
        self.assertEqual(doble.llamadas, [])
        self.assertEqual(Cobro.objects.count(), 0)

    def test_parametro_invalido_del_puerto_es_400(self) -> None:
        self._entrar(self.usuario_a)
        with patch(
            "ventas.servicio.obtener_puerto",
            return_value=_PuertoParametroInvalido(),
        ):
            respuesta = self.client.post(
                _RUTA,
                {"monto": "0.01", "referencia": "7"},
                format="json",
            )
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("num_ref", respuesta.json()["detail"])
        self.assertEqual(Cobro.objects.count(), 0)
        self.assertEqual(Movimiento.objects.count(), 0)

    def test_venta_de_a_no_aparece_en_movimientos_de_b(self) -> None:
        self._entrar(self.usuario_a)
        with patch("ventas.servicio.obtener_puerto", return_value=_Espia()):
            alta = self.client.post(
                _RUTA,
                {"monto": "0.01", "concepto": "Solo A"},
                format="json",
            )
        self.assertEqual(alta.status_code, 201)
        movimiento_id = alta.json()["movimiento_id"]

        self._entrar(self.usuario_b)
        ajeno = self.client.get("/api/movimientos/")
        self.assertEqual(ajeno.status_code, 200)
        self.assertNotIn(movimiento_id, [item["id"] for item in ajeno.json()])

        self._entrar(self.usuario_a)
        propio = self.client.get("/api/movimientos/")
        self.assertEqual(propio.status_code, 200)
        self.assertIn(movimiento_id, [item["id"] for item in propio.json()])
