"""Venta por notificación. El puerto es el adaptador de desarrollo o un doble."""

import json
import threading
import time
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from ambito.models import Comercio, Membresia
from movimientos.models import Cobro, Movimiento
from pey.desarrollo import AdaptadorDesarrollo
from pey.produccion import AdaptadorProduccion
from pey.tipos import ErrorPey, NotificacionCreada, QrCreado
from sesion.middleware import _MENSAJE_SIN_SESION
from ventas.servicio import (
    MontoInvalido,
    TelefonoInvalido,
    crear_venta_notificacion,
)
from webhooks.tests.support.pey_webhook import SECRETO, post_firmado

_RUTA = "/api/ventas/notificacion/"
_RUTA_QR = "/api/ventas/"
_TELEFONO = "5512345678"
_MENSAJE_VIVA = "Ya hay una venta pendiente."


class _Doble:
    def __init__(self) -> None:
        self.llamadas: list[tuple] = []

    def cuenta_active(self, comercio: Comercio) -> bool:
        self.llamadas.append(("cuenta_active", comercio.pk))
        return True

    def crear_notificacion(self, **kwargs) -> NotificacionCreada:
        self.llamadas.append(("crear_notificacion", kwargs))
        raise AssertionError("no debe crear la notificación")

    def crear_qr(self, **kwargs) -> QrCreado:
        self.llamadas.append(("crear_qr", kwargs))
        raise AssertionError("no debe crear el qr")


class _Espia(AdaptadorDesarrollo):
    def __init__(self, fallar_con: ErrorPey | None = None) -> None:
        super().__init__(fallar_con=fallar_con)
        self.notificaciones: list[dict] = []
        self.qrs: list[dict] = []
        self.creada: NotificacionCreada | None = None

    def crear_notificacion(self, **kwargs) -> NotificacionCreada:
        self.notificaciones.append(kwargs)
        creada = super().crear_notificacion(**kwargs)
        self.creada = creada
        return creada

    def crear_qr(self, **kwargs) -> QrCreado:
        self.qrs.append(kwargs)
        return super().crear_qr(**kwargs)


def _textos(obj) -> list[str]:
    valores = []
    for campo in obj._meta.concrete_fields:
        valor = getattr(obj, campo.attname)
        if isinstance(valor, str):
            valores.append(valor)
    return valores


class NotificacionVentaTests(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.comercio = Comercio.objects.create(
            nombre="Comercio A",
            semilla_active_dev=True,
        )
        self.usuario = User.objects.create_user(username="vendedor_pn", password="pass")
        Membresia.objects.create(usuario=self.usuario, comercio=self.comercio)

    def _entrar(self) -> None:
        self.client.force_login(self.usuario)

    def _post(self, puerto, cuerpo=None):
        with patch("ventas.servicio.obtener_puerto", return_value=puerto):
            return self.client.post(
                _RUTA,
                cuerpo
                or {"monto": "25.00", "telefono": _TELEFONO, "concepto": "Aviso"},
                format="json",
            )

    def test_montos_y_telefonos_invalidos_no_llaman_al_puerto(self) -> None:
        self._entrar()
        doble = _Doble()
        montos = ("0", "-1", "1000000.01", "0.005")
        for monto in montos:
            with self.subTest(monto=monto):
                with patch("ventas.servicio.obtener_puerto", return_value=doble):
                    respuesta = self.client.post(
                        _RUTA,
                        {"monto": monto, "telefono": _TELEFONO},
                        format="json",
                    )
                self.assertEqual(respuesta.status_code, 400)
                self.assertIn("monto", respuesta.json())
                with self.assertRaises(MontoInvalido):
                    crear_venta_notificacion(
                        comercio=self.comercio,
                        monto=Decimal(monto),
                        telefono=_TELEFONO,
                        concepto="",
                        referencia="",
                        puerto=doble,
                    )
        for telefono in ("551234567", "55123456789", "551234567A", "551 234567"):
            with self.subTest(telefono=telefono):
                with patch("ventas.servicio.obtener_puerto", return_value=doble):
                    respuesta = self.client.post(
                        _RUTA,
                        {"monto": "10.00", "telefono": telefono},
                        format="json",
                    )
                self.assertEqual(respuesta.status_code, 400)
                self.assertIn("telefono", respuesta.json())
                with self.assertRaises(TelefonoInvalido):
                    crear_venta_notificacion(
                        comercio=self.comercio,
                        monto=Decimal("10.00"),
                        telefono=telefono,
                        concepto="",
                        referencia="",
                        puerto=doble,
                    )
        self.assertEqual(doble.llamadas, [])
        self.assertEqual(Cobro.objects.count(), 0)

        espia = _Espia()
        tope = self._post(espia, {"monto": "1000000", "telefono": _TELEFONO})
        self.assertEqual(tope.status_code, 201)
        self.assertEqual(tope.json()["monto"], "1000000.00")
        self.assertEqual(espia.notificaciones[0]["monto"], Decimal("1000000.00"))

    @override_settings(PEY_WEBHOOK_SECRET=SECRETO)
    def test_aviso_pn_marca_pagado_una_vez(self) -> None:
        self._entrar()
        alta = self._post(_Espia())
        self.assertEqual(alta.status_code, 201)
        cobro = Cobro.objects.get(pk=alta.json()["cobro_id"])
        cuerpo = json.dumps(
            {
                "type": "codi.pn.payment_received",
                "amount": 25,
                "concept": "Aviso",
                "transactionId": cobro.pey_transaction_id,
            },
            separators=(",", ":"),
        )
        aviso = post_firmado(self.client, cuerpo, "msg_pn_venta")
        self.assertEqual(aviso.status_code, 200)
        self.assertEqual(aviso.json(), {"estado": "aplicado"})
        movimiento = Movimiento.objects.get(pk=alta.json()["movimiento_id"])
        self.assertEqual(movimiento.estado, Movimiento.Estado.PAGADO)
        self.assertEqual(movimiento.pey_transaction_id, cobro.pey_transaction_id)

        otro_id = post_firmado(self.client, cuerpo, "msg_pn_venta_otro")
        self.assertEqual(otro_id.status_code, 200)
        self.assertEqual(otro_id.json(), {"estado": "duplicado_transaccion"})
        self.assertEqual(
            Movimiento.objects.filter(estado=Movimiento.Estado.PAGADO).count(),
            1,
        )

        mismo_id = post_firmado(self.client, cuerpo, "msg_pn_venta")
        self.assertEqual(mismo_id.status_code, 200)
        self.assertEqual(mismo_id.json(), {"estado": "duplicado"})
        self.assertEqual(
            Movimiento.objects.filter(estado=Movimiento.Estado.PAGADO).count(),
            1,
        )

    def test_un_canal_vivo_entre_qr_y_notificacion(self) -> None:
        self._entrar()
        qr = _Espia()
        with patch("ventas.servicio.obtener_puerto", return_value=qr):
            alta_qr = self.client.post(
                _RUTA_QR,
                {"monto": "0.01", "concepto": "QR"},
                format="json",
            )
        self.assertEqual(alta_qr.status_code, 201)
        aviso = _Espia()
        bloqueada = self._post(aviso)
        self.assertEqual(bloqueada.status_code, 409)
        self.assertEqual(bloqueada.json()["detail"], _MENSAJE_VIVA)
        self.assertEqual(bloqueada.json()["canal"], Movimiento.Canal.QR_VENTA)
        self.assertEqual(aviso.notificaciones, [])

        cobro_qr = Cobro.objects.get(pk=alta_qr.json()["cobro_id"])
        cobro_qr.vence_en = timezone.now() - timedelta(seconds=5)
        cobro_qr.save(update_fields=["vence_en"])
        alta_pn = self._post(aviso)
        self.assertEqual(alta_pn.status_code, 201)
        self.assertEqual(len(aviso.notificaciones), 1)
        self.assertEqual(
            Movimiento.objects.get(pk=alta_qr.json()["movimiento_id"]).estado,
            Movimiento.Estado.VENCIDO,
        )

        bloqueo = _Espia()
        with patch("ventas.servicio.obtener_puerto", return_value=bloqueo):
            otra_qr = self.client.post(
                _RUTA_QR,
                {"monto": "0.01"},
                format="json",
            )
        self.assertEqual(otra_qr.status_code, 409)
        self.assertEqual(otra_qr.json()["canal"], Movimiento.Canal.NOTIFICACION)
        self.assertEqual(bloqueo.qrs, [])

        cobro_pn = Cobro.objects.get(pk=alta_pn.json()["cobro_id"])
        cobro_pn.vence_en = timezone.now() - timedelta(seconds=5)
        cobro_pn.save(update_fields=["vence_en"])
        with patch("ventas.servicio.obtener_puerto", return_value=bloqueo):
            qr_final = self.client.post(
                _RUTA_QR,
                {"monto": "0.01", "concepto": "Después"},
                format="json",
            )
        self.assertEqual(qr_final.status_code, 201)
        self.assertEqual(len(bloqueo.qrs), 1)

    def test_exito_guarda_la_notificacion_sin_el_telefono(self) -> None:
        self._entrar()
        espia = _Espia()
        antes = timezone.now()
        with self.assertLogs("ventas.servicio", level="INFO") as logs:
            with patch("ventas.servicio.obtener_puerto", return_value=espia):
                respuesta = self.client.post(
                    _RUTA,
                    {
                        "monto": "0.01",
                        "telefono": _TELEFONO,
                        "concepto": "Aviso",
                        "referencia": "7",
                    },
                    format="json",
                )
        despues = timezone.now()
        self.assertEqual(respuesta.status_code, 201)
        cuerpo = respuesta.json()
        self.assertEqual(cuerpo["telefono_final"], "5678")
        self.assertEqual(cuerpo["canal"], "notificacion")
        self.assertEqual(cuerpo["estado"], "pendiente")
        self.assertEqual(cuerpo["origen"], "origen_desarrollo")
        self.assertNotIn(_TELEFONO, json.dumps(cuerpo))
        texto = " ".join(logs.output)
        self.assertNotIn(_TELEFONO, texto)
        self.assertIn("telefono_final=5678", texto)

        cobro = Cobro.objects.get(pk=cuerpo["cobro_id"])
        movimiento = Movimiento.objects.get(pk=cuerpo["movimiento_id"])
        self.assertEqual(cobro.canal, Movimiento.Canal.NOTIFICACION)
        self.assertTrue(cobro.pey_transaction_id.startswith("dev-tx-"))
        self.assertIsNone(cobro.pey_qr_id)
        self.assertEqual(cobro.qr_string, "")
        self.assertGreaterEqual(cobro.vence_en, antes + timedelta(seconds=600))
        self.assertLessEqual(cobro.vence_en, despues + timedelta(seconds=600))
        self.assertEqual(movimiento.cobro_id, cobro.pk)
        self.assertEqual(movimiento.estado, Movimiento.Estado.PENDIENTE)
        self.assertEqual(movimiento.origen, Movimiento.Origen.ORIGEN_DESARROLLO)
        self.assertEqual(espia.notificaciones[0]["telefono"], _TELEFONO)
        self.assertEqual(espia.notificaciones[0]["num_ref"], "7")
        self.assertEqual(espia.notificaciones[0]["expiracion_s"], 600)
        for valor in _textos(cobro) + _textos(movimiento):
            self.assertNotIn(_TELEFONO, valor)

    def test_error_pey_cuenta_sesion_y_comercio(self) -> None:
        respuesta = self.client.post(
            _RUTA,
            {"monto": "1.00", "telefono": _TELEFONO},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(respuesta.json()["detail"], _MENSAJE_SIN_SESION)

        self._entrar()
        espia = _Espia(
            fallar_con=ErrorPey("INVALID_STATE", "rechazado", "req-pn", False),
        )
        fallo = self._post(espia)
        self.assertEqual(fallo.status_code, 502)
        self.assertEqual(fallo.json()["tipo"], "INVALID_STATE")
        self.assertEqual(fallo.json()["request_id"], "req-pn")
        self.assertNotIn(_TELEFONO, json.dumps(fallo.json()))
        self.assertEqual(Cobro.objects.count(), 0)
        self.assertEqual(Movimiento.objects.count(), 0)

        inactivo = Comercio.objects.create(nombre="Sin cuenta", semilla_active_dev=False)
        usuario = User.objects.create_user(username="sin_cuenta", password="pass")
        Membresia.objects.create(usuario=usuario, comercio=inactivo)
        self.client.force_login(usuario)
        sin_llamada = _Espia()
        cuenta = self._post(sin_llamada)
        self.assertEqual(cuenta.status_code, 409)
        self.assertEqual(cuenta.json(), {"detail": "La cuenta no está ACTIVE."})
        self.assertEqual(sin_llamada.notificaciones, [])

        self.client.force_login(self.usuario)
        comercio = self.client.post(
            _RUTA,
            {
                "monto": "1.00",
                "telefono": _TELEFONO,
                "comercio": inactivo.pk,
            },
            format="json",
        )
        self.assertEqual(comercio.status_code, 400)
        self.assertIn("comercio", comercio.json()["detail"].lower())
        self.assertEqual(Cobro.objects.count(), 0)

    def test_502_distingue_si_la_notificacion_pudo_llegar(self) -> None:
        self._entrar()
        detalle_posible = (
            "Puede que la notificación le haya llegado al cliente. "
            "Confírmelo con él antes de reintentar."
        )
        casos = (
            (False, "pey no pudo crear el cobro."),
            (True, detalle_posible),
        )
        for puede, detalle in casos:
            with self.subTest(puede_haberse_creado=puede):
                espia = _Espia(
                    fallar_con=ErrorPey(
                        "NO_DISPONIBLE",
                        "timeout",
                        "req-puede",
                        puede_haberse_creado=puede,
                    ),
                )
                respuesta = self._post(espia)
                self.assertEqual(respuesta.status_code, 502)
                cuerpo = respuesta.json()
                self.assertEqual(cuerpo["puede_haberse_creado"], puede)
                self.assertEqual(cuerpo["detail"], detalle)
                self.assertEqual(cuerpo["tipo"], "NO_DISPONIBLE")
                self.assertEqual(cuerpo["request_id"], "req-puede")
                self.assertNotIn(_TELEFONO, json.dumps(cuerpo))
        self.assertEqual(Cobro.objects.count(), 0)

    def test_fallo_de_bd_loguea_transaction_id_sin_el_telefono(self) -> None:
        self._entrar()
        espia = _Espia()
        with self.assertLogs("ventas", level="ERROR") as logs:
            with patch("ventas.servicio.obtener_puerto", return_value=espia):
                with patch(
                    "ventas.servicio.Movimiento.objects.create",
                    side_effect=RuntimeError("bd"),
                ):
                    with self.assertRaises(RuntimeError):
                        self.client.post(
                            _RUTA,
                            {
                                "monto": "0.01",
                                "telefono": _TELEFONO,
                                "concepto": "Aviso",
                            },
                            format="json",
                        )
        self.assertIsNotNone(espia.creada)
        texto = " ".join(logs.output)
        self.assertIn(espia.creada.transaction_id, texto)
        self.assertIn("telefono_final=5678", texto)
        self.assertNotIn(_TELEFONO, texto)
        self.assertEqual(Cobro.objects.count(), 0)
        self.assertEqual(Movimiento.objects.count(), 0)

    @override_settings(PEY_API_KEY="llave-de-prueba")
    def test_adaptador_produccion_envia_el_cuerpo_pn(self) -> None:
        self.comercio.pey_codi_status = self.comercio.PeyCodiStatus.ACTIVE
        self.comercio.save(update_fields=["pey_codi_status"])
        self._entrar()
        llamadas: list[tuple] = []

        def transporte(metodo, url, headers, cuerpo, timeout):
            llamadas.append((metodo, url, dict(headers), cuerpo, timeout))
            return (
                200,
                b'{"transactionId":"tx-prod-pn","codiId":"12345678901234567890"}',
            )

        puerto = AdaptadorProduccion(transporte=transporte)
        with patch("urllib.request.urlopen", side_effect=AssertionError("red")):
            with patch("ventas.servicio.obtener_puerto", return_value=puerto):
                respuesta = self.client.post(
                    _RUTA,
                    {
                        "monto": "10.00",
                        "telefono": _TELEFONO,
                        "concepto": "Aviso",
                        "referencia": "42",
                    },
                    format="json",
                )
        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(respuesta.json()["origen"], "origen_pey")
        self.assertNotIn("llave-de-prueba", json.dumps(respuesta.json()))
        self.assertEqual(len(llamadas), 1)
        metodo, url, headers, cuerpo, _timeout = llamadas[0]
        self.assertEqual(metodo, "POST")
        self.assertTrue(url.endswith("/codi/pn"))
        self.assertIn("llave-de-prueba", headers["Authorization"])
        enviado = json.loads(cuerpo)
        self.assertEqual(enviado["amount"], 10)
        self.assertEqual(enviado["phoneNumber"], _TELEFONO)
        self.assertEqual(enviado["concept"], "Aviso")
        self.assertEqual(enviado["expiration"], 600)
        self.assertEqual(enviado["numRef"], "42")
        movimiento = Movimiento.objects.get(pk=respuesta.json()["movimiento_id"])
        self.assertEqual(movimiento.origen, Movimiento.Origen.ORIGEN_PEY)
        self.assertEqual(movimiento.cobro.pey_transaction_id, "tx-prod-pn")


class _PuertoCruzado:
    def __init__(self, ambos: threading.Event) -> None:
        self.ambos = ambos
        self.llamadas = 0
        self._candado = threading.Lock()

    def cuenta_active(self, comercio: Comercio) -> bool:
        return True

    def _pasar(self) -> int:
        with self._candado:
            self.llamadas += 1
            numero = self.llamadas
        if not self.ambos.wait(timeout=5):
            raise TimeoutError("el otro hilo no llegó al candado")
        time.sleep(0.1)
        return numero

    def crear_qr(self, **kwargs) -> QrCreado:
        numero = self._pasar()
        return QrCreado(
            id=f"qr-cruz-{numero}",
            qr_string=f"cody-dev://qr/qr-cruz-{numero}",
        )

    def crear_notificacion(self, **kwargs) -> NotificacionCreada:
        numero = self._pasar()
        return NotificacionCreada(
            transaction_id=f"tx-cruz-{numero}",
            codi_id="12345678901234567890",
        )


class ConcurrenciaQrYNotificacionTests(TransactionTestCase):
    def test_qr_y_notificacion_simultaneos_dejan_un_solo_cobro(self) -> None:
        comercio = Comercio.objects.create(nombre="Cruzado", semilla_active_dev=True)
        usuario = User.objects.create_user(username="cruzado", password="pass")
        Membresia.objects.create(usuario=usuario, comercio=comercio)
        ambos = threading.Event()
        barrera = threading.Barrier(2)
        puerto = _PuertoCruzado(ambos)
        codigos: list[int] = []
        errores: list[BaseException] = []
        candado = threading.Lock()
        candado_llegada = threading.Lock()
        llegados = [0]
        cliente_qr = APIClient()
        cliente_pn = APIClient()
        cliente_qr.force_login(usuario)
        cliente_pn.force_login(usuario)

        def alta(cliente: APIClient, ruta: str, cuerpo: dict) -> None:
            connections.close_all()
            try:
                barrera.wait(timeout=5)
                with candado_llegada:
                    llegados[0] += 1
                    if llegados[0] >= 2:
                        ambos.set()
                respuesta = cliente.post(ruta, cuerpo, format="json")
                with candado:
                    codigos.append(respuesta.status_code)
            except BaseException as exc:
                errores.append(exc)
            finally:
                connections.close_all()

        with patch("ventas.servicio.obtener_puerto", return_value=puerto):
            hilos = [
                threading.Thread(
                    target=alta,
                    args=(cliente_qr, _RUTA_QR, {"monto": "0.01", "concepto": "QR"}),
                ),
                threading.Thread(
                    target=alta,
                    args=(
                        cliente_pn,
                        _RUTA,
                        {"monto": "0.01", "telefono": _TELEFONO, "concepto": "Aviso"},
                    ),
                ),
            ]
            for hilo in hilos:
                hilo.start()
            for hilo in hilos:
                hilo.join(timeout=8)
                self.assertFalse(hilo.is_alive())

        self.assertEqual(errores, [])
        self.assertEqual(sorted(codigos), [201, 409])
        self.assertEqual(puerto.llamadas, 1)
        self.assertEqual(Cobro.objects.filter(comercio=comercio).count(), 1)
