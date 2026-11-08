"""Vistas de alta de cobros acotadas al comercio de la sesión."""

import logging

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ambito.exceptions import (
    AmbitoError,
    ComercioEnCuerpoError,
    CuentaNoActiveError,
    SinAmbitoError,
)
from ambito.scope import preparar_operacion_cobro
from movimientos.alta_qr_general import alta_qr_general
from pey.tipos import ErrorPey, ParametroInvalido

logger = logging.getLogger(__name__)

_MENSAJE_PEY = "pey no pudo crear el cobro."


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
        except CuentaNoActiveError as exc:
            return Response(
                {
                    "detail": str(exc),
                    "tipo": "INVALID_STATE",
                },
                status=400,
            )
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

        status = 201 if resultado.creado else 200
        return Response(
            {
                "qr_string": resultado.cobro.qr_string,
                "pey_qr_id": resultado.cobro.pey_qr_id,
            },
            status=status,
        )
