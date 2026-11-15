"""Implementación persistente del puerto núcleo-canal v1."""

from decimal import Decimal
from functools import wraps
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import IntegrityError, InterfaceError, OperationalError

from ambito.models import Comercio
from pedidos.contratos.v1 import (
    CodigoError,
    ContextoCanalV1,
    ContextoConsumidorV1,
    RespuestaV1,
)
from pedidos.contratos.validacion import ErrorContrato, hash_canonico, validar_comando
from pedidos.errores import ErrorNucleo
from pedidos.models import Pedido, RenglonPedido
from pedidos.servicios import aceptaciones, solicitudes
from pedidos.servicios.eventos import consultar
from pedidos.servicios.presentacion import pedido_dto


def respuesta(funcion):
    @wraps(funcion)
    def ejecutar(*args, **kwargs):
        try:
            return funcion(*args, **kwargs)
        except ErrorContrato as exc:
            return RespuestaV1(
                False, error=ErrorNucleo(exc.codigo, exc.detalle).error()
            )
        except ErrorNucleo as exc:
            return RespuestaV1(False, error=exc.error())
        except IntegrityError:
            return RespuestaV1(
                False, error=ErrorNucleo(CodigoError.PAYLOAD_INVALIDO).error()
            )
        except (OperationalError, InterfaceError):
            return RespuestaV1(
                False,
                error=ErrorNucleo(
                    CodigoError.SERVICIO_NO_DISPONIBLE, retryable=True
                ).error(),
            )

    return ejecutar


class NucleoRealV1:
    ES_SIMULACION = False

    def __init__(self, lector):
        self.lector = lector

    def _preparar(self, operacion, ctx, datos, mensaje=None):
        validar_comando(operacion, datos)
        tipo = (
            ContextoConsumidorV1
            if operacion == "consultar_eventos"
            else ContextoCanalV1
        )
        if not isinstance(ctx, tipo) or any(
            not isinstance(v, str) or not v.strip() for v in ctx.a_dict().values()
        ):
            raise ErrorNucleo(CodigoError.CONTEXTO_INVALIDO)
        limites = {
            "instancia_id": 64,
            "sesion_id": 64,
            "conversacion_id": 64,
            "cliente_externo_id": 128,
        }
        if any(len(valor) > limites[campo] for campo, valor in ctx.a_dict().items()):
            raise ErrorNucleo(CodigoError.CONTEXTO_INVALIDO)
        if len(datos.get("message_key", "")) > 400:
            raise ErrorNucleo(CodigoError.PAYLOAD_INVALIDO)
        comercio_id = self.lector.resolver_comercio(ctx)
        try:
            comercio = (
                Comercio.objects.filter(pk=comercio_id).first() if comercio_id else None
            )
        except (ValueError, TypeError, ValidationError):
            comercio = None
        if not comercio:
            raise ErrorNucleo(CodigoError.CONTEXTO_INVALIDO)
        if mensaje:
            origen = self.lector.leer_mensaje(ctx, datos[mensaje])
            if (
                not origen
                or origen.mensaje_id != datos[mensaje]
                or not origen.origen_autenticado
                or not isinstance(origen.texto_normalizado, str)
                or len(origen.texto_normalizado) > 4000
                or (
                    "message_key" in datos
                    and (
                        origen.message_key != datos["message_key"]
                        or origen.secuencia_conversacion
                        != datos["secuencia_conversacion"]
                    )
                )
            ):
                raise ErrorNucleo(CodigoError.CONTEXTO_INVALIDO)
        return comercio, hash_canonico(operacion, datos, ctx)

    def _pedido(self, comercio, ctx, pedido_id, bloquear=False):
        qs = Pedido.objects.select_for_update() if bloquear else Pedido.objects
        pedido = qs.filter(
            comercio=comercio,
            pk=pedido_id,
            instancia_id=ctx.instancia_id,
            sesion_id=ctx.sesion_id,
            conversacion_id=ctx.conversacion_id,
            cliente_externo_id=ctx.cliente_externo_id,
        ).first()
        if not pedido:
            raise ErrorNucleo(CodigoError.PEDIDO_NO_ACCESIBLE)
        return pedido

    @respuesta
    def registrar_solicitud(self, ctx, **datos):
        return solicitudes.registrar_solicitud(self, ctx, **datos)

    def _renglones(self, pedido, renglones):
        existentes = {str(r.id): r for r in pedido.renglones.all()}
        ids = []
        for posicion, item in enumerate(renglones, 1):
            d = item if isinstance(item, dict) else item.a_dict()
            identidad = str(UUID(d["renglon_id"]))
            ids.append(identidad)
            r = existentes.get(identidad)
            nuevo = r is None
            if nuevo:
                if RenglonPedido.objects.filter(pk=identidad).exists():
                    raise ErrorNucleo(CodigoError.PAYLOAD_INVALIDO)
                r = RenglonPedido(id=identidad, pedido=pedido)
            elif (
                r.texto_solicitado,
                r.cantidad_solicitada,
                r.unidad_solicitada,
            ) != (
                d["texto_solicitado"],
                Decimal(str(d["cantidad_solicitada"]))
                if d.get("cantidad_solicitada") is not None
                else None,
                d.get("unidad_solicitada"),
            ):
                r.descripcion, r.cantidad, r.unidad = "", None, ""
                r.precio_unitario_centavos, r.resolucion, r.motivo_exclusion = (
                    None,
                    "pendiente",
                    "",
                )
            r.posicion = posicion + 1000
            r.texto_solicitado = d["texto_solicitado"]
            r.cantidad_solicitada = d.get("cantidad_solicitada")
            r.unidad_solicitada = d.get("unidad_solicitada")
            r.save(force_insert=nuevo)
        pedido.renglones.exclude(id__in=ids).delete()
        for posicion, identidad in enumerate(ids, 1):
            pedido.renglones.filter(id=identidad).update(posicion=posicion)

    @respuesta
    def corregir_borrador(self, ctx, **datos):
        return solicitudes.corregir_borrador(self, ctx, **datos)

    @respuesta
    def consultar_pedido(self, ctx, **datos):
        comercio, _ = self._preparar("consultar_pedido", ctx, datos)
        return RespuestaV1(
            True,
            data={
                "pedido": pedido_dto(self._pedido(comercio, ctx, datos["pedido_id"]))
            },
        )

    @respuesta
    def aceptar_cotizacion(self, ctx, **datos):
        return aceptaciones.aceptar_cotizacion(self, ctx, **datos)

    @respuesta
    def solicitar_cobro(self, ctx, **datos):
        from pedidos.servicios.cobros import solicitar
        comercio, huella = self._preparar("solicitar_cobro", ctx, datos)
        pedido = self._pedido(comercio, ctx, datos["pedido_id"])
        return solicitar(comercio, pedido, datos, huella)

    @respuesta
    def consultar_eventos(self, ctx, **datos):
        comercio, _ = self._preparar("consultar_eventos", ctx, datos)
        return RespuestaV1(
            True,
            data=consultar(comercio, ctx, datos["cursor"], datos.get("limite", 50)),
        )
