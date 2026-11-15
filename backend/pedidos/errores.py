"""Errores del núcleo y su representación HTTP."""

from pedidos.contratos.v1 import CodigoError, ErrorV1


class ErrorNucleo(Exception):
    def __init__(self, codigo, detalle="Operación rechazada.", **datos):
        self.codigo = CodigoError(codigo)
        self.detalle = detalle
        self.datos = datos
        super().__init__(detalle)

    def error(self):
        accion = {
            CodigoError.VERSION_OBSOLETA: "consultar_pedido",
            CodigoError.REVISION_OBSOLETA: "consultar_pedido",
            CodigoError.PEDIDO_ABIERTO: "consultar_pedido",
            CodigoError.PROVEEDOR_NO_DISPONIBLE: "consultar_pedido",
            CodigoError.RENGLON_PENDIENTE: "corregir",
        }.get(self.codigo, "ninguna")
        return ErrorV1(self.codigo, self.detalle, next_action=accion, **self.datos)


def estado_http(codigo):
    if codigo in (
        CodigoError.PAYLOAD_INVALIDO,
        CodigoError.VERSION_CONTRATO_NO_SOPORTADA,
    ):
        return 400
    if codigo in (CodigoError.CONTEXTO_INVALIDO, CodigoError.PERMISO_DENEGADO):
        return 403
    if codigo == CodigoError.PEDIDO_NO_ACCESIBLE:
        return 404
    if codigo in (
        CodigoError.SERVICIO_NO_DISPONIBLE,
        CodigoError.PROVEEDOR_NO_DISPONIBLE,
    ):
        return 503
    return 409
