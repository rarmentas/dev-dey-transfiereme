"""GET /api/ventas/<id>/ — estado guardado del movimiento de venta.

La consulta de respaldo a pey no entra en esta historia.
"""

from decimal import Decimal

from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ambito.exceptions import AmbitoError, ComercioEnCuerpoError, SinAmbitoError
from ambito.scope import rechazar_comercio_en_query, requerir_comercio
from movimientos.exceptions import TransicionInvalida
from movimientos.models import Movimiento
from ventas.canal import CANALES_VENTA

_CENTAVO = Decimal("0.01")
_MENSAJE_NO_ENCONTRADO = "No encontrado."


def _respuesta_ambito(exc: AmbitoError, status: int) -> Response:
    return Response({"detail": str(exc)}, status=status)


def _vencer_si_cumplio_el_plazo(movimiento: Movimiento) -> None:
    """Vencido perezoso: el mismo criterio que `vencer_pendientes` de la 3.2."""
    cobro = movimiento.cobro
    if movimiento.estado != Movimiento.Estado.PENDIENTE or cobro is None:
        return
    if cobro.vence_en is None or cobro.vence_en > timezone.now():
        return
    try:
        movimiento.cambiar_estado(Movimiento.Estado.VENCIDO)
    except TransicionInvalida:
        movimiento.refresh_from_db()


def _estado_json(movimiento: Movimiento) -> dict:
    cobro = movimiento.cobro
    vence_en = None
    qr_string = ""
    if cobro is not None:
        if cobro.vence_en is not None:
            vence_en = cobro.vence_en.isoformat()
        qr_string = cobro.qr_string or ""
    pagado_en = None
    if movimiento.pagado_en is not None:
        pagado_en = movimiento.pagado_en.isoformat()
    return {
        "movimiento_id": movimiento.pk,
        "canal": movimiento.canal,
        "estado": movimiento.estado,
        "monto": format(movimiento.monto.quantize(_CENTAVO), "f"),
        "concepto": movimiento.concepto,
        "vence_en": vence_en,
        "pagado_en": pagado_en,
        "qr_string": qr_string,
    }


class EstadoVentaView(APIView):
    """Lee el estado guardado. Otro comercio o un canal que no es de venta: 404."""

    permission_classes = [IsAuthenticated]

    def get(self, request, movimiento_id: int):
        try:
            rechazar_comercio_en_query(request.GET)
            comercio = requerir_comercio(request)
        except ComercioEnCuerpoError as exc:
            return _respuesta_ambito(exc, 400)
        except SinAmbitoError as exc:
            return _respuesta_ambito(exc, 403)

        movimiento = (
            Movimiento.objects.select_related("cobro")
            .filter(comercio=comercio, pk=movimiento_id)
            .first()
        )
        if movimiento is None or movimiento.canal not in CANALES_VENTA:
            return Response({"detail": _MENSAJE_NO_ENCONTRADO}, status=404)

        _vencer_si_cumplio_el_plazo(movimiento)
        return Response(_estado_json(movimiento))
