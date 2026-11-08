"""Venta por notificación. El puerto es el adaptador de desarrollo o un doble."""

import json
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

    def crear_notificacion(self, **kwargs) -> NotificacionCreada:
        self.notificaciones.append(kwargs)
        return super().crear_notificacion(**kwargs)

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
