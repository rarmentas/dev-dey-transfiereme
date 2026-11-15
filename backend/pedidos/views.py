"""API autenticada de revisión de pedidos."""

from uuid import UUID

from django.db import InterfaceError, OperationalError
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from ambito.exceptions import ComercioEnCuerpoError, SinAmbitoError
from ambito.scope import (
    preparar_operacion_cobro,
    rechazar_comercio_en_query,
    requerir_comercio,
)
from pedidos.contratos.v1 import CodigoError
from pedidos.contratos.validacion import ErrorContrato
from pedidos.errores import ErrorNucleo
from pedidos.http import error, exito
from pedidos.models import Pedido
from pedidos.serializers import validar_cuerpo
from pedidos.servicios.presentacion import pedido_dto
from pedidos.servicios.tendero import operar


def _comercio(request, escritura=False):
    rechazar_comercio_en_query(request.GET)
    if escritura:
        datos = request.data
        return preparar_operacion_cobro(
            request, datos if isinstance(datos, dict) else {}
        )
    return requerir_comercio(request)


def _pedido(comercio, pedido_id):
    try:
        identificador = UUID(pedido_id)
    except (ValueError, TypeError, AttributeError):
        raise ErrorNucleo(CodigoError.PEDIDO_NO_ACCESIBLE) from None
    pedido = Pedido.objects.filter(comercio=comercio, pk=identificador).first()
    if not pedido:
        raise ErrorNucleo(CodigoError.PEDIDO_NO_ACCESIBLE)
    return pedido


def capturar(funcion):
    def ejecutar(*args, **kwargs):
        try:
            return funcion(*args, **kwargs)
        except ComercioEnCuerpoError as exc:
            return error(ErrorNucleo(CodigoError.PAYLOAD_INVALIDO, str(exc)))
        except SinAmbitoError as exc:
            return error(ErrorNucleo(CodigoError.PERMISO_DENEGADO, str(exc)))
        except ErrorContrato as exc:
            return error(ErrorNucleo(exc.codigo, exc.detalle))
        except ErrorNucleo as exc:
            return error(exc)
        except (OperationalError, InterfaceError):
            return error(
                ErrorNucleo(CodigoError.SERVICIO_NO_DISPONIBLE, retryable=True)
            )

    return ejecutar


class ListaPedidosView(APIView):
    permission_classes = [IsAuthenticated]

    @capturar
    def get(self, request):
        comercio = _comercio(request)
        lista = []
        for pedido in Pedido.objects.filter(comercio=comercio).order_by(
            "-actualizado_en"
        )[:100]:
            dto = pedido_dto(pedido)
            cot = dto.cotizacion
            lista.append(
                {
                    "id": dto.id,
                    "numero": dto.numero,
                    "estado": dto.estado,
                    "version": dto.version,
                    "abierto": dto.abierto,
                    "cliente_etiqueta": dto.cliente_etiqueta,
                    "renglones_total": len(dto.renglones),
                    "renglones_pendientes": sum(
                        r.resolucion.value == "pendiente" for r in dto.renglones
                    ),
                    "total_comercial_centavos": cot.total_comercial_centavos
                    if cot
                    else None,
                    "importe_efectivo_centavos": cot.importe_efectivo_centavos
                    if cot
                    else None,
                    "cotizacion_revision": cot.revision if cot else None,
                    "aceptado": dto.aceptacion is not None,
                    "pago_estado": "sin_cobro",
                    "preparacion": "pendiente",
                    "creado_en": pedido.creado_en,
                    "actualizado_en": pedido.actualizado_en,
                }
            )
        return exito({"pedidos": lista})


class DetallePedidoView(APIView):
    permission_classes = [IsAuthenticated]

    @capturar
    def get(self, request, pedido_id):
        return exito(pedido_dto(_pedido(_comercio(request), pedido_id)))


class RenglonesPedidoView(APIView):
    permission_classes = [IsAuthenticated]

    @capturar
    def put(self, request, pedido_id):
        comercio = _comercio(request, True)
        pedido = _pedido(comercio, pedido_id)
        datos = validar_cuerpo(request.data, revision=True)
        resultado = operar(
            comercio, pedido.id, "revisar_renglones", datos, request.user
        )
        return exito(resultado.data["pedido"], replayed=resultado.replayed)


class CotizacionesPedidoView(APIView):
    permission_classes = [IsAuthenticated]

    @capturar
    def post(self, request, pedido_id):
        comercio = _comercio(request, True)
        pedido = _pedido(comercio, pedido_id)
        datos = validar_cuerpo(request.data)
        resultado = operar(
            comercio, pedido.id, "publicar_cotizacion", datos, request.user
        )
        return exito(
            resultado.data["pedido"],
            status=200 if resultado.replayed else 201,
            replayed=resultado.replayed,
        )
