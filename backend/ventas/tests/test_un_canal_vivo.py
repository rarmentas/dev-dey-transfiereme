"""Una venta viva por comercio. El puerto es falso: nadie sale a la red."""

import threading
import time
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import connections
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from ambito.models import Comercio, Membresia
from movimientos.models import Cobro, Movimiento
from pey.desarrollo import AdaptadorDesarrollo
from pey.tipos import ErrorPey, QrCreado
from ventas.canal import exigir_sin_venta_viva

_RUTA = "/api/ventas/"
_MENSAJE_VIVA = "Ya hay una venta pendiente."


class _Espia(AdaptadorDesarrollo):
    def __init__(self, fallar_con: ErrorPey | None = None) -> None:
        super().__init__(fallar_con=fallar_con)
        self.qr_kwargs: list[dict] = []

    def crear_qr(self, **kwargs) -> QrCreado:
        self.qr_kwargs.append(kwargs)
        return super().crear_qr(**kwargs)


class _PuertoEspera:
    """El primero en crear_qr espera a que el otro hilo ya esté en el candado."""

    def __init__(self, ambos: threading.Event) -> None:
        self.ambos = ambos
        self.llamadas = 0
        self._candado = threading.Lock()

    def cuenta_active(self, comercio: Comercio) -> bool:
        return True

    def crear_qr(self, **kwargs) -> QrCreado:
        with self._candado:
            self.llamadas += 1
            numero = self.llamadas
        if not self.ambos.wait(timeout=5):
            raise TimeoutError("el otro hilo no llegó al candado")
        time.sleep(0.1)
        return QrCreado(
            id=f"qr-conc-{numero}",
            qr_string=f"cody-dev://qr/qr-conc-{numero}",
        )


class UnCanalVivoTests(TestCase):
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
        self.usuario_a = User.objects.create_user(username="vendedor_a", password="pass-a")
        self.usuario_b = User.objects.create_user(username="vendedor_b", password="pass-b")
        Membresia.objects.create(usuario=self.usuario_a, comercio=self.comercio_a)
        Membresia.objects.create(usuario=self.usuario_b, comercio=self.comercio_b)

    def _entrar(self, usuario: User) -> None:
        self.client.force_login(usuario)

    def _post(self, puerto, cuerpo=None):
        with patch("ventas.servicio.obtener_puerto", return_value=puerto):
            return self.client.post(
                _RUTA,
                cuerpo or {"monto": "0.01", "concepto": "Taco"},
                format="json",
            )

    def _cobro(self, comercio: Comercio, **kwargs) -> Cobro:
        canal = kwargs.get("canal", Movimiento.Canal.QR_VENTA)
        datos = {
            "comercio": comercio,
            "canal": canal,
            "monto": Decimal("0") if canal == Movimiento.Canal.QR_GENERAL else Decimal("10.00"),
            "concepto": "Transferencia",
            "vence_en": timezone.now() + timedelta(minutes=10),
        }
        if canal == Movimiento.Canal.NOTIFICACION:
            datos["pey_transaction_id"] = kwargs.pop(
                "pey_transaction_id",
                f"tx-{comercio.pk}-{Cobro.objects.count()}",
            )
        else:
            datos["pey_qr_id"] = kwargs.pop(
                "pey_qr_id",
                f"qr-{comercio.pk}-{Cobro.objects.count()}",
            )
            datos["qr_string"] = kwargs.pop("qr_string", "cody-dev://qr/fijo")
        datos.update(kwargs)
        return Cobro.objects.create(**datos)

    def _movimiento(self, cobro: Cobro, **kwargs) -> Movimiento:
        datos = {
            "comercio": cobro.comercio,
            "cobro": cobro,
            "monto": cobro.monto if cobro.monto > 0 else Decimal("10.00"),
            "concepto": cobro.concepto,
            "canal": cobro.canal,
            "estado": Movimiento.Estado.PENDIENTE,
            "origen": Movimiento.Origen.ORIGEN_DESARROLLO,
        }
        datos.update(kwargs)
        return Movimiento.objects.create(**datos)

    def test_segunda_venta_qr_responde_409_y_no_crea_otro_cobro(self) -> None:
        self._entrar(self.usuario_a)
        espia = _Espia()
        primera = self._post(espia)
        self.assertEqual(primera.status_code, 201)
        segunda = self._post(espia)
        self.assertEqual(segunda.status_code, 409)
        cuerpo = segunda.json()
        self.assertEqual(cuerpo["detail"], _MENSAJE_VIVA)
        self.assertEqual(cuerpo["movimiento_id"], primera.json()["movimiento_id"])
        self.assertEqual(cuerpo["canal"], Movimiento.Canal.QR_VENTA)
        self.assertEqual(cuerpo["vence_en"], primera.json()["vence_en"])
        self.assertEqual(len(espia.qr_kwargs), 1)
        self.assertEqual(Cobro.objects.count(), 1)

    def test_notificacion_pendiente_bloquea_el_qr(self) -> None:
        aviso = self._cobro(
            self.comercio_a,
            canal=Movimiento.Canal.NOTIFICACION,
            pey_transaction_id="tx-aviso-vivo",
        )
        movimiento = self._movimiento(aviso)
        self._entrar(self.usuario_a)
        espia = _Espia()
        respuesta = self._post(espia)
        self.assertEqual(respuesta.status_code, 409)
        cuerpo = respuesta.json()
        self.assertEqual(cuerpo["detail"], _MENSAJE_VIVA)
        self.assertEqual(cuerpo["movimiento_id"], movimiento.pk)
        self.assertEqual(cuerpo["canal"], Movimiento.Canal.NOTIFICACION)
        self.assertEqual(espia.qr_kwargs, [])
        self.assertEqual(Cobro.objects.filter(canal=Movimiento.Canal.QR_VENTA).count(), 0)

    def test_pendiente_vencido_se_cierra_y_la_nueva_venta_pasa(self) -> None:
        cobro = self._cobro(
            self.comercio_a,
            vence_en=timezone.now() - timedelta(seconds=30),
            pey_qr_id="qr-ya-vencido",
        )
        anterior = self._movimiento(cobro)
        self._entrar(self.usuario_a)
        respuesta = self._post(_Espia())
        self.assertEqual(respuesta.status_code, 201)
        anterior.refresh_from_db()
        self.assertEqual(anterior.estado, Movimiento.Estado.VENCIDO)
        self.assertEqual(Cobro.objects.count(), 2)
        self.assertEqual(
            Movimiento.objects.filter(estado=Movimiento.Estado.PENDIENTE).count(),
            1,
        )

    def test_pagado_vencido_y_qr_general_no_bloquean(self) -> None:
        escenarios = (
            ("pagado", Movimiento.Estado.PAGADO, Movimiento.Canal.QR_VENTA),
            ("vencido", Movimiento.Estado.VENCIDO, Movimiento.Canal.QR_VENTA),
            ("general pendiente", Movimiento.Estado.PENDIENTE, Movimiento.Canal.QR_GENERAL),
            ("general pagado", Movimiento.Estado.PAGADO, Movimiento.Canal.QR_GENERAL),
        )
        for nombre, estado, canal in escenarios:
            with self.subTest(nombre=nombre):
                comercio = Comercio.objects.create(
                    nombre=nombre,
                    semilla_active_dev=True,
                )
                usuario = User.objects.create_user(username=nombre.replace(" ", "_"), password="pass")
                Membresia.objects.create(usuario=usuario, comercio=comercio)
                vence = (
                    None
                    if canal == Movimiento.Canal.QR_GENERAL
                    else timezone.now() + timedelta(minutes=5)
                )
                cobro = self._cobro(comercio, canal=canal, vence_en=vence)
                self._movimiento(cobro, estado=estado)
                self._entrar(usuario)
                antes = Cobro.objects.filter(
                    comercio=comercio,
                    canal=Movimiento.Canal.QR_VENTA,
                ).count()
                respuesta = self._post(_Espia())
                self.assertEqual(respuesta.status_code, 201)
                self.assertEqual(
                    Cobro.objects.filter(
                        comercio=comercio,
                        canal=Movimiento.Canal.QR_VENTA,
                    ).count(),
                    antes + 1,
                )

    def test_venta_viva_de_a_no_bloquea_a_b(self) -> None:
        self._entrar(self.usuario_a)
        espia = _Espia()
        alta_a = self._post(espia)
        self.assertEqual(alta_a.status_code, 201)
        self._entrar(self.usuario_b)
        alta_b = self._post(espia)
        self.assertEqual(alta_b.status_code, 201)
        self.assertEqual(len(espia.qr_kwargs), 2)
        self.assertEqual(Cobro.objects.filter(comercio=self.comercio_a).count(), 1)
        self.assertEqual(Cobro.objects.filter(comercio=self.comercio_b).count(), 1)

    def test_vence_en_nulo_bloquea_y_no_se_vence(self) -> None:
        cobro = self._cobro(
            self.comercio_a,
            vence_en=None,
            pey_qr_id="qr-sin-vence",
        )
        movimiento = self._movimiento(cobro)
        self._entrar(self.usuario_a)
        espia = _Espia()
        respuesta = self._post(espia)
        self.assertEqual(respuesta.status_code, 409)
        cuerpo = respuesta.json()
        self.assertEqual(cuerpo["detail"], _MENSAJE_VIVA)
        self.assertEqual(cuerpo["movimiento_id"], movimiento.pk)
        self.assertIsNone(cuerpo["vence_en"])
        self.assertEqual(espia.qr_kwargs, [])
        movimiento.refresh_from_db()
        self.assertEqual(movimiento.estado, Movimiento.Estado.PENDIENTE)
        self.assertEqual(Cobro.objects.count(), 1)

    def test_vence_en_igual_a_ahora_no_bloquea_y_se_vence(self) -> None:
        momento = timezone.now()
        cobro = self._cobro(
            self.comercio_a,
            vence_en=momento,
            pey_qr_id="qr-justo-ahora",
        )
        anterior = self._movimiento(cobro)
        self._entrar(self.usuario_a)
        with patch("ventas.canal.timezone.now", return_value=momento):
            respuesta = self._post(_Espia())
        self.assertEqual(respuesta.status_code, 201)
        anterior.refresh_from_db()
        self.assertEqual(anterior.estado, Movimiento.Estado.VENCIDO)
        self.assertEqual(
            Movimiento.objects.filter(estado=Movimiento.Estado.PENDIENTE).count(),
            1,
        )

    def test_error_pey_no_revierte_el_vencido_perezoso(self) -> None:
        cobro = self._cobro(
            self.comercio_a,
            vence_en=timezone.now() - timedelta(seconds=30),
            pey_qr_id="qr-por-vencer",
        )
        anterior = self._movimiento(cobro)
        self.assertEqual(anterior.estado, Movimiento.Estado.PENDIENTE)
        self._entrar(self.usuario_a)
        espia = _Espia(
            fallar_con=ErrorPey("INVALID_STATE", "rechazado", "req-vence", False),
        )
        respuesta = self._post(espia)
        self.assertEqual(respuesta.status_code, 502)
        anterior.refresh_from_db()
        self.assertEqual(anterior.estado, Movimiento.Estado.VENCIDO)
        self.assertEqual(list(Cobro.objects.values_list("pk", flat=True)), [cobro.pk])
        self.assertFalse(
            Movimiento.objects.filter(estado=Movimiento.Estado.PENDIENTE).exists()
        )

    def test_error_pey_con_venta_vencida_no_deja_cobro_nuevo(self) -> None:
        cobro = self._cobro(
            self.comercio_a,
            vence_en=timezone.now() - timedelta(minutes=5),
            pey_qr_id="qr-vencido-previo",
        )
        anterior = self._movimiento(cobro, estado=Movimiento.Estado.VENCIDO)
        self._entrar(self.usuario_a)
        espia = _Espia(
            fallar_con=ErrorPey("INVALID_STATE", "rechazado", "req-vivo", False),
        )
        respuesta = self._post(espia)
        self.assertEqual(respuesta.status_code, 502)
        self.assertEqual(list(Cobro.objects.values_list("pk", flat=True)), [cobro.pk])
        anterior.refresh_from_db()
        self.assertEqual(anterior.estado, Movimiento.Estado.VENCIDO)
        self.assertFalse(
            Movimiento.objects.filter(estado=Movimiento.Estado.PENDIENTE).exists()
        )


class ConcurrenciaUnCanalTests(TransactionTestCase):
    def test_exigir_sin_venta_viva_fuera_de_atomic_falla(self) -> None:
        with self.assertRaises(RuntimeError):
            exigir_sin_venta_viva(Comercio(pk=1))

    def test_dos_altas_simultaneas_dejan_un_solo_cobro(self) -> None:
        comercio = Comercio.objects.create(nombre="Concurrente", semilla_active_dev=True)
        usuario = User.objects.create_user(username="concurrente", password="pass")
        Membresia.objects.create(usuario=usuario, comercio=comercio)
        ambos = threading.Event()
        barrera = threading.Barrier(2)
        puerto = _PuertoEspera(ambos)
        codigos: list[int] = []
        detalles: list[str] = []
        errores: list[BaseException] = []
        candado = threading.Lock()
        candado_llegada = threading.Lock()
        llegados = [0]
        clientes = [APIClient(), APIClient()]
        for cliente in clientes:
            cliente.force_login(usuario)

        def alta(cliente: APIClient) -> None:
            connections.close_all()
            try:
                barrera.wait(timeout=5)
                with candado_llegada:
                    llegados[0] += 1
                    if llegados[0] >= 2:
                        ambos.set()
                respuesta = cliente.post(
                    _RUTA,
                    {"monto": "0.01", "concepto": "Taco"},
                    format="json",
                )
                with candado:
                    codigos.append(respuesta.status_code)
                    detalles.append(respuesta.json().get("detail", ""))
            except BaseException as exc:
                errores.append(exc)
            finally:
                connections.close_all()

        with patch("ventas.servicio.obtener_puerto", return_value=puerto):
            hilos = [
                threading.Thread(target=alta, args=(cliente,)) for cliente in clientes
            ]
            for hilo in hilos:
                hilo.start()
            for hilo in hilos:
                hilo.join(timeout=8)
                self.assertFalse(hilo.is_alive())

        self.assertEqual(errores, [])
        self.assertEqual(sorted(codigos), [201, 409])
        self.assertIn("Ya hay una venta pendiente.", detalles)
        self.assertEqual(puerto.llamadas, 1)
        self.assertEqual(Cobro.objects.filter(comercio=comercio).count(), 1)
        self.assertEqual(
            Movimiento.objects.filter(
                comercio=comercio,
                estado=Movimiento.Estado.PENDIENTE,
            ).count(),
            1,
        )
