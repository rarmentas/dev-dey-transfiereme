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
from pedidos.servicios.entrega import operar as operar_entrega
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


def _con_entrega(pedido, dto):
    """DTO con la autoría de preparación coherente con su estado."""
    datos = dto.a_dict()
    listo = dto.preparacion.value in ("listo", "entregado")
    entregado = dto.preparacion.value == "entregado"
    datos["entrega"] = {
        "listo_en": pedido.listo_en if listo else None,
        "listo_por": pedido.listo_por_id if listo else None,
        "entregado_en": pedido.entregado_en if entregado else None,
        "entregado_por": pedido.entregado_por_id if entregado else None,
    }
    return datos


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
                    "pago_estado": dto.pago_estado.value,
                    "preparacion": dto.preparacion.value,
                    "creado_en": pedido.creado_en,
                    "actualizado_en": pedido.actualizado_en,
                }
            )
        return exito({"pedidos": lista})


class DetallePedidoView(APIView):
    permission_classes = [IsAuthenticated]

    @capturar
    def get(self, request, pedido_id):
        pedido = _pedido(_comercio(request), pedido_id)
        return exito(_con_entrega(pedido, pedido_dto(pedido)))


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


class ListoPedidoView(APIView):
    permission_classes = [IsAuthenticated]

    @capturar
    def post(self, request, pedido_id):
        comercio = _comercio(request, True)
        pedido = _pedido(comercio, pedido_id)
        resultado = operar_entrega(
            comercio, pedido.id, validar_cuerpo(request.data), request.user
        )
        pedido.refresh_from_db()
        return exito(
            _con_entrega(pedido, resultado.data["pedido"]),
            replayed=resultado.replayed,
        )


class EntregadoPedidoView(APIView):
    permission_classes = [IsAuthenticated]

    @capturar
    def post(self, request, pedido_id):
        comercio = _comercio(request, True)
        pedido = _pedido(comercio, pedido_id)
        resultado = operar_entrega(
            comercio, pedido.id, validar_cuerpo(request.data), request.user,
            entregado=True,
        )
        pedido.refresh_from_db()
        return exito(
            _con_entrega(pedido, resultado.data["pedido"]),
            replayed=resultado.replayed,
        )


class CobroPedidoView(APIView):
    permission_classes = [IsAuthenticated]

    @capturar
    def post(self, request, pedido_id):
        from pedidos.contratos.validacion import hash_canonico, validar_comando
        from pedidos.servicios.cobros import activar_espera, solicitar

        comercio = _comercio(request, True)
        pedido = _pedido(comercio, pedido_id)
        if not isinstance(request.data, dict):
            raise ErrorNucleo(CodigoError.PAYLOAD_INVALIDO)
        cuerpo = dict(request.data)
        accion = cuerpo.pop("accion", "")
        if accion == "activar_espera":
            intento_id = cuerpo.pop("intento_id", "")
            try:
                intento_id = UUID(intento_id)
            except (TypeError, ValueError, AttributeError):
                raise ErrorNucleo(CodigoError.PAYLOAD_INVALIDO) from None
            datos = validar_cuerpo(cuerpo)
            resultado = activar_espera(comercio, pedido.pk, intento_id, datos)
            return exito(resultado.data["pedido"], replayed=resultado.replayed)
        if accion != "solicitar":
            raise ErrorNucleo(CodigoError.PAYLOAD_INVALIDO)
        aceptacion = pedido.cotizaciones.filter(
            revision=pedido.revision_vigente, aceptacion__isnull=False
        ).first()
        if not aceptacion:
            raise ErrorNucleo(CodigoError.ACEPTACION_REQUERIDA)
        datos = {
            **cuerpo,
            "contrato_version": cuerpo.get("contrato_version", "1.0"),
            "pedido_id": str(pedido.pk),
            "aceptacion_id": str(aceptacion.aceptacion.pk),
            "canal": cuerpo.get("canal", "qr_venta"),
        }
        validar_comando("solicitar_cobro", datos)
        huella = hash_canonico("solicitar_cobro", datos, str(comercio.pk))
        resultado = solicitar(comercio, pedido, datos, huella)
        return exito(
            resultado.data["pedido"], status=200 if resultado.replayed else 201,
            replayed=resultado.replayed,
        )
