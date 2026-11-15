"""Vistas de cuenta del comercio (ámbito por sesión)."""

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ambito.cuenta import cuenta_por_defecto
from ambito.cuenta_pey_servicio import enmascarar_clabe
from ambito.exceptions import AmbitoError, ComercioEnCuerpoError, SinAmbitoError
from ambito.scope import (
    preparar_operacion_cobro,
    rechazar_comercio_en_query,
    requerir_comercio,
)

_MENSAJE_CLABE_INVALIDA = "Indique una CLABE válida de 18 dígitos."
_MENSAJE_CUERPO = "El cuerpo debe ser un objeto JSON."
_MENSAJE_SOLO_NOMBRE = "Solo puede enviar nombre."
_MENSAJE_NOMBRE_TEXTO = "El nombre debe ser texto."
_MENSAJE_NOMBRE_VACIO = "Indique el nombre del comercio."
_MENSAJE_NOMBRE_LARGO = "El nombre del comercio no puede pasar de 200 caracteres."
_LARGO_NOMBRE = 200


def _respuesta_ambito(exc: AmbitoError, status: int) -> Response:
    return Response({"detail": str(exc)}, status=status)


class GuardarClabeView(APIView):
    """Lee o persiste la CLABE en el comercio de la sesión."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            rechazar_comercio_en_query(request.GET)
            comercio = requerir_comercio(request)
        except ComercioEnCuerpoError as exc:
            return _respuesta_ambito(exc, 400)
        except SinAmbitoError as exc:
            return _respuesta_ambito(exc, 403)

        if not getattr(request, "es_dueno", False):
            return Response({"codigo": "NO_ES_DUENO"}, status=403)
        cuenta = cuenta_por_defecto(comercio)
        return Response({"clabe": enmascarar_clabe(cuenta.clabe) if cuenta else ""})

    def post(self, request):
        return Response({"codigo": "USAR_CUENTAS"}, status=409)


class ActualizarComercioView(APIView):
    """Actualiza el nombre del comercio de la sesión."""

    permission_classes = [IsAuthenticated]

    def patch(self, request):
        datos = request.data if isinstance(request.data, dict) else None
        if datos is None:
            return Response({"detail": _MENSAJE_CUERPO}, status=400)
        try:
            comercio = preparar_operacion_cobro(request, datos)
        except ComercioEnCuerpoError as exc:
            return _respuesta_ambito(exc, 400)
        except SinAmbitoError as exc:
            return _respuesta_ambito(exc, 403)

        if set(datos) != {"nombre"}:
            return Response({"detail": _MENSAJE_SOLO_NOMBRE}, status=400)
        crudo = datos["nombre"]
        if not isinstance(crudo, str):
            return Response({"detail": _MENSAJE_NOMBRE_TEXTO}, status=400)
        nombre = crudo.strip()
        if nombre == "":
            return Response({"detail": _MENSAJE_NOMBRE_VACIO}, status=400)
        if len(nombre) > _LARGO_NOMBRE:
            return Response({"detail": _MENSAJE_NOMBRE_LARGO}, status=400)

        comercio.nombre = nombre
        comercio.save(update_fields=["nombre"])
        return Response({"id": comercio.pk, "nombre": comercio.nombre})
