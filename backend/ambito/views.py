"""Vistas de cuenta del comercio (ámbito por sesión)."""

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ambito.clabe import clabe_es_valida
from ambito.exceptions import AmbitoError, ComercioEnCuerpoError, SinAmbitoError
from ambito.scope import preparar_operacion_cobro

_MENSAJE_CLABE_INVALIDA = "Indique una CLABE válida de 18 dígitos."


def _respuesta_ambito(exc: AmbitoError, status: int) -> Response:
    return Response({"detail": str(exc)}, status=status)


class GuardarClabeView(APIView):
    """Persiste la CLABE en el comercio de la sesión."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        datos = request.data if isinstance(request.data, dict) else {}
        try:
            comercio = preparar_operacion_cobro(request, datos)
        except ComercioEnCuerpoError as exc:
            return _respuesta_ambito(exc, 400)
        except SinAmbitoError as exc:
            return _respuesta_ambito(exc, 403)

        clabe_raw = datos.get("clabe")
        if not isinstance(clabe_raw, str):
            clabe_raw = ""
        clabe = clabe_raw.strip()
        if not clabe_es_valida(clabe):
            return Response({"detail": _MENSAJE_CLABE_INVALIDA}, status=400)

        comercio.clabe = clabe
        comercio.save(update_fields=["clabe"])
        return Response({"clabe": comercio.clabe})
