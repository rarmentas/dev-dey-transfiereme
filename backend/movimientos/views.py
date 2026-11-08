"""Vistas de lectura de movimientos acotadas al comercio de la sesión."""

from datetime import date, timedelta
from decimal import Decimal

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
from movimientos.tablero import (
    Fila,
    ZONA_NOMBRE,
    agrupar,
    inicio_dia_local,
    interpretar_dia,
    partir_por_origen,
)

_CENTAVO = Decimal("0.01")

_MENSAJE_NO_ENCONTRADO = "No encontrado."


def _respuesta_ambito(exc: AmbitoError, status: int) -> Response:
    return Response({"detail": str(exc)}, status=status)


def _parametro_dia(valor: str | None) -> date | None:
    if valor is None:
        return None
    return interpretar_dia(valor)


def _texto_monto(valor: Decimal) -> str:
    return format(valor.quantize(_CENTAVO), "f")


def _fila_json(fila: Fila) -> dict:
    return {
        "dia": fila.dia.isoformat(),
        "canal": fila.canal,
        "concepto": fila.concepto,
        "etiqueta": fila.etiqueta,
        "total": _texto_monto(fila.total),
        "cantidad": fila.cantidad,
    }


def _bloque(filas: list[Fila]) -> dict:
    total = sum((fila.total for fila in filas), Decimal("0"))
    return {"filas": [_fila_json(fila) for fila in filas], "total": _texto_monto(total)}


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


class TableroView(APIView):
    """Agrupa lo pagado del comercio. No mezcla origen_pey con origen_desarrollo."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            rechazar_comercio_en_query(request.GET)
            comercio = requerir_comercio(request)
        except ComercioEnCuerpoError as exc:
            return _respuesta_ambito(exc, 400)
        except SinAmbitoError as exc:
            return _respuesta_ambito(exc, 403)

        try:
            desde = _parametro_dia(request.GET.get("desde"))
            hasta = _parametro_dia(request.GET.get("hasta"))
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)

        pagados = filtrar_por_comercio(
            Movimiento.objects.filter(estado=Movimiento.Estado.PAGADO),
            comercio,
        )
        if desde is not None:
            pagados = pagados.filter(pagado_en__gte=inicio_dia_local(desde))
        if hasta is not None:
            pagados = pagados.filter(
                pagado_en__lt=inicio_dia_local(hasta + timedelta(days=1))
            )
        confirmado, desarrollo = partir_por_origen(pagados)
        return Response(
            {
                "zona": ZONA_NOMBRE,
                "confirmado": _bloque(agrupar(confirmado)),
                "desarrollo": _bloque(agrupar(desarrollo)),
            }
        )
