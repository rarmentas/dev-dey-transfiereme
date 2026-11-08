"""Vistas de movimientos acotadas al comercio de la sesión."""

from datetime import date, timedelta
from decimal import Decimal

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ambito.exceptions import AmbitoError, ComercioEnCuerpoError, SinAmbitoError
from ambito.scope import (
    filtrar_por_comercio,
    obtener_por_id_en_ambito,
    preparar_operacion_cobro,
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
_MENSAJE_CUERPO = "El cuerpo debe ser un objeto JSON."
_MENSAJE_SOLO_VISIBLE = "Solo puede enviar concepto_visible."
_MENSAJE_TEXTO = "El concepto visible debe ser texto."
_MENSAJE_VACIO = "Indique el concepto visible."
_MENSAJE_LARGO = "El concepto visible no puede pasar de 500 caracteres."
_MENSAJE_SOLO_PAGADO = "Solo se puede renombrar un movimiento cobrado."
_LARGO_VISIBLE = 500


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
    """Detalle y renombre del concepto visible, si el movimiento es del comercio."""

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

    def patch(self, request, pk: int):
        datos = request.data
        if not isinstance(datos, dict):
            return Response({"detail": _MENSAJE_CUERPO}, status=400)
        try:
            rechazar_comercio_en_query(request.GET)
            comercio = preparar_operacion_cobro(request, datos)
        except ComercioEnCuerpoError as exc:
            return _respuesta_ambito(exc, 400)
        except SinAmbitoError as exc:
            return _respuesta_ambito(exc, 403)

        if set(datos) != {"concepto_visible"}:
            return Response({"detail": _MENSAJE_SOLO_VISIBLE}, status=400)
        crudo = datos["concepto_visible"]
        if not isinstance(crudo, str):
            return Response({"detail": _MENSAJE_TEXTO}, status=400)
        visible = crudo.strip()
        if visible == "":
            return Response({"detail": _MENSAJE_VACIO}, status=400)
        if len(visible) > _LARGO_VISIBLE:
            return Response({"detail": _MENSAJE_LARGO}, status=400)

        movimiento = obtener_por_id_en_ambito(
            Movimiento.objects.select_related("cobro"),
            comercio,
            pk,
        )
        if movimiento is None:
            return Response({"detail": _MENSAJE_NO_ENCONTRADO}, status=404)
        if movimiento.estado != Movimiento.Estado.PAGADO:
            return Response({"detail": _MENSAJE_SOLO_PAGADO}, status=409)

        movimiento.concepto_visible = visible
        movimiento.save(update_fields=["concepto_visible", "actualizado_en"])
        return Response(MovimientoLecturaSerializer(movimiento).data)


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
