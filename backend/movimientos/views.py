"""Vistas de lectura de movimientos acotadas al comercio de la sesión."""

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ambito.exceptions import AmbitoError, ComercioEnCuerpoError, SinAmbitoError
from ambito.scope import (
    filtrar_por_comercio,
    obtener_por_id_en_ambito,
    rechazar_comercio_en_query,
    requerir_comercio,
)
from movimientos.models import Movimiento
from movimientos.serializers import MovimientoLecturaSerializer

_MENSAJE_NO_ENCONTRADO = "No encontrado."


def _respuesta_ambito(exc: AmbitoError, status: int) -> Response:
    return Response({"detail": str(exc)}, status=status)


class ListadoMovimientosView(APIView):
    """Lista los movimientos del comercio de la sesión."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            rechazar_comercio_en_query(request.GET)
            comercio = requerir_comercio(request)
        except ComercioEnCuerpoError as exc:
            return _respuesta_ambito(exc, 400)
        except SinAmbitoError as exc:
            return _respuesta_ambito(exc, 403)

        queryset = filtrar_por_comercio(Movimiento.objects.all(), comercio)
        serializer = MovimientoLecturaSerializer(queryset, many=True)
        return Response(serializer.data)


class DetalleMovimientoView(APIView):
    """Detalle de un movimiento si pertenece al comercio de la sesión."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk: int):
        try:
            rechazar_comercio_en_query(request.GET)
            comercio = requerir_comercio(request)
        except ComercioEnCuerpoError as exc:
            return _respuesta_ambito(exc, 400)
        except SinAmbitoError as exc:
            return _respuesta_ambito(exc, 403)

        movimiento = obtener_por_id_en_ambito(Movimiento.objects.all(), comercio, pk)
        if movimiento is None:
            return Response({"detail": _MENSAJE_NO_ENCONTRADO}, status=404)

        serializer = MovimientoLecturaSerializer(movimiento)
        return Response(serializer.data)
