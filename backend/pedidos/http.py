"""Sobres HTTP de pedidos."""

from rest_framework.response import Response

from pedidos.contratos.v1 import serializar
from pedidos.errores import estado_http


def exito(data, status=200, replayed=False):
    return Response(
        {
            "contrato_version": "1.0",
            "ok": True,
            "replayed": replayed,
            "data": serializar(data),
        },
        status=status,
    )


def error(exc):
    dato = exc.error()
    return Response(
        {
            "contrato_version": "1.0",
            "ok": False,
            "codigo": dato.code.value,
            "detail": dato.detail,
            "retryable": dato.retryable,
            "next_action": dato.next_action,
            "pedido_id": dato.pedido_id,
            "pedido_version": dato.pedido_version,
            "errores": getattr(exc, "errores", None),
        },
        status=estado_http(dato.code),
    )
