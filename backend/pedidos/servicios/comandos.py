"""Idempotencia de comandos bajo el candado del comercio."""

from pedidos.contratos.v1 import CodigoError, RespuestaV1
from pedidos.errores import ErrorNucleo
from pedidos.models import ComandoNucleo
from pedidos.servicios.presentacion import pedido_desde_json, pedido_dto


def repeticion(comercio, operacion, clave, huella):
    anterior = ComandoNucleo.objects.filter(
        comercio=comercio, operacion=operacion, command_key=clave
    ).first()
    if anterior is None:
        return None
    if anterior.hash_payload != huella:
        raise ErrorNucleo(CodigoError.CLAVE_REUTILIZADA)
    pedido = pedido_desde_json(anterior.resultado)
    data = {"pedido": pedido}
    if operacion == "solicitar_cobro" and pedido.pago_estado.value == "en_espera":
        data["espera"] = "COBRO_OCUPADO"
    return RespuestaV1(True, replayed=True, data=data)


def guardar(comercio, operacion, clave, huella, pedido, replayed=False):
    dto = pedido_dto(pedido)
    ComandoNucleo.objects.create(
        comercio=comercio,
        operacion=operacion,
        command_key=clave,
        hash_payload=huella,
        pedido=pedido,
        resultado=dto.a_dict(),
    )
    return RespuestaV1(True, replayed=replayed, data={"pedido": dto})
