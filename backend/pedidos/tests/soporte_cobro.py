"""Puerto bancario determinista para pruebas de cobro."""

from django.db import connection
from pey.tipos import NotificacionCreada, QrCreado

from pedidos.models import IntentoCobro


class PuertoPeyFalso:
    def __init__(self):
        self.llamadas = []
        self.fallar_con = None
        self.siguiente_id = "qr-prueba"

    def crear_qr(self, **datos):
        if connection.in_atomic_block:
            raise AssertionError("La red se llamó dentro de una transacción")
        self.llamadas.append(("qr", datos))
        if not IntentoCobro.objects.filter(estado="enviando").exists():
            raise AssertionError("No hay intento durable en estado enviando")
        if self.fallar_con:
            raise self.fallar_con
        return QrCreado(self.siguiente_id, "qr-prueba")

    def crear_notificacion(self, **datos):
        if connection.in_atomic_block:
            raise AssertionError("La red se llamó dentro de una transacción")
        self.llamadas.append(("notificacion", datos))
        if not IntentoCobro.objects.filter(estado="enviando").exists():
            raise AssertionError("No hay intento durable en estado enviando")
        if self.fallar_con:
            raise self.fallar_con
        return NotificacionCreada(self.siguiente_id, "codi")


class ClienteLegacy:
    """Cliente que entrega claves distintas a las altas legacy heredadas."""

    @staticmethod
    def crear():
        from uuid import uuid4

        from rest_framework.test import APIClient

        class Cliente(APIClient):
            def post(self, path, data=None, format=None, **extra):
                extra.setdefault("HTTP_IDEMPOTENCY_KEY", str(uuid4()))
                return super().post(path, data=data, format=format, **extra)

        return Cliente()


def firmar_aviso(cuerpo, mensaje_id, cuando):
    """Firma un aviso de prueba con el helper de webhooks."""
    from webhooks.tests.support.pey_webhook import encabezados

    return encabezados(cuerpo, mensaje_id, cuando)
