"""POST /api/ventas/ — alta de QR de venta para el comercio de la sesión."""

import json
import logging
from decimal import Decimal, InvalidOperation

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ambito.exceptions import AmbitoError, ComercioEnCuerpoError, SinAmbitoError
from ambito.scope import preparar_operacion_cobro, rechazar_comercio_en_query
from pey.tipos import ErrorPey, ParametroInvalido
from ventas.canal import VentaPendiente
from ventas.serializers import CrearVentaSerializer, venta_creada_a_json
from ventas.servicio import CuentaNoActive, ValidacionVenta, crear_venta_qr

logger = logging.getLogger(__name__)

_MENSAJE_CUERPO = "El cuerpo debe ser un objeto JSON."
_MENSAJE_CUENTA = "La cuenta no está ACTIVE."
_MENSAJE_VENTA_VIVA = "Ya hay una venta pendiente."
_MENSAJE_PEY = "pey no pudo crear el cobro."


class _CuerpoInvalido(Exception):
    def __init__(self) -> None:
        super().__init__(_MENSAJE_CUERPO)


def _leer_cuerpo(request) -> dict:
    bruto = request.body
    if not bruto:
        raise _CuerpoInvalido()
    try:
        datos = json.loads(bruto.decode("utf-8"), parse_float=Decimal)
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValueError,
        InvalidOperation,
    ) as exc:
        raise _CuerpoInvalido() from exc
    if not isinstance(datos, dict):
        raise _CuerpoInvalido()
    return datos


def _respuesta_ambito(exc: AmbitoError, status: int) -> Response:
    return Response({"detail": str(exc)}, status=status)


def _venta_pendiente(exc: VentaPendiente) -> dict:
    movimiento = exc.movimiento
    cobro = movimiento.cobro
    return {
        "detail": _MENSAJE_VENTA_VIVA,
        "movimiento_id": movimiento.pk,
        "canal": movimiento.canal,
        "vence_en": cobro.vence_en.isoformat() if cobro.vence_en is not None else None,
    }


class CrearVentaView(APIView):
    """Crea un cobro qr_venta pendiente. Exige sesión; el comercio sale de ella."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            datos = _leer_cuerpo(request)
        except _CuerpoInvalido as exc:
            return Response({"detail": str(exc)}, status=400)

        try:
            rechazar_comercio_en_query(request.GET)
            comercio = preparar_operacion_cobro(request, datos)
        except ComercioEnCuerpoError as exc:
            return _respuesta_ambito(exc, 400)
        except SinAmbitoError as exc:
            return _respuesta_ambito(exc, 403)

        serializer = CrearVentaSerializer(data=datos)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        limpio = serializer.validated_data
        try:
            venta = crear_venta_qr(
                comercio=comercio,
                monto=limpio["monto"],
                concepto=limpio["concepto"],
                referencia=limpio["referencia"],
            )
        except ValidacionVenta as exc:
            return Response({exc.campo: [str(exc)]}, status=400)
        except CuentaNoActive:
            return Response({"detail": _MENSAJE_CUENTA}, status=409)
        except VentaPendiente as exc:
            return Response(_venta_pendiente(exc), status=409)
        except ParametroInvalido as exc:
            return Response({"detail": str(exc)}, status=400)
        except ErrorPey as exc:
            logger.warning(
                "pey no pudo crear el cobro tipo=%s request_id=%s comercio_id=%s",
                exc.tipo,
                exc.request_id,
                comercio.pk,
            )
            return Response(
                {
                    "detail": _MENSAJE_PEY,
                    "tipo": exc.tipo,
                    "request_id": exc.request_id,
                    "puede_haberse_creado": exc.puede_haberse_creado,
                },
                status=502,
            )

        return Response(venta_creada_a_json(venta), status=201)
