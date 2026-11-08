"""Vistas de alta de cobros acotadas al comercio de la sesión."""

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ambito.exceptions import AmbitoError, ComercioEnCuerpoError, SinAmbitoError
from ambito.scope import preparar_operacion_cobro
from movimientos.alta_qr_general import alta_qr_general
from movimientos.exceptions import CuentaInactivaParaCobro

_MENSAJE_CUENTA_INACTIVA = (
    "La cuenta no está activa. No puede dar de alta el QR general."
)


def _respuesta_ambito(exc: AmbitoError, status: int) -> Response:
    return Response({"detail": str(exc)}, status=status)


class AltaQrGeneralView(APIView):
    """Crea o devuelve el QR general del comercio de la sesión."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        datos = request.data if isinstance(request.data, dict) else {}
        try:
            comercio = preparar_operacion_cobro(request, datos)
        except ComercioEnCuerpoError as exc:
            return _respuesta_ambito(exc, 400)
        except SinAmbitoError as exc:
            return _respuesta_ambito(exc, 403)

        try:
            resultado = alta_qr_general(comercio)
        except CuentaInactivaParaCobro:
            return Response(
                {
                    "detail": _MENSAJE_CUENTA_INACTIVA,
                    "tipo": "INVALID_STATE",
                },
                status=400,
            )

        status = 201 if resultado.creado else 200
        return Response(
            {
                "qr_string": resultado.cobro.qr_string,
                "pey_qr_id": resultado.cobro.pey_qr_id,
            },
            status=status,
        )
