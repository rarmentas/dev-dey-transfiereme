from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from sesion import codigos

_MENSAJE_ALTA_ENVIADO = (
    "Enviamos un código a su correo. Revise su bandeja de entrada."
)
_MENSAJE_ALTA_LISTA = "Su cuenta quedó lista. Ya puede entrar."
_MENSAJE_OLVIDO_ENVIADO = (
    "Si existe una cuenta con ese correo, recibirá un código en breve."
)
_MENSAJE_OLVIDO_LISTO = "Su contraseña quedó actualizada. Ya puede entrar."


def _texto(data, *claves: str, recortar: bool = True) -> str:
    for clave in claves:
        valor = data.get(clave)
        if isinstance(valor, str):
            return valor.strip() if recortar else valor
    return ""


def _contrasena(data) -> str:
    return _texto(data, "contraseña", "contrasena", "password", recortar=False)


def _correo_normalizado(data) -> str:
    return codigos.normalizar_correo(_texto(data, "correo"))


class _BasePublica(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(ensure_csrf_cookie, name="dispatch")
class AltaSolicitarView(_BasePublica):
    def post(self, request):
        correo = _correo_normalizado(request.data)
        contrasena = _contrasena(request.data)
        if not correo or not contrasena:
            return Response(
                {"detail": "Indique su correo y contraseña."},
                status=400,
            )
        ok, detalle = codigos.solicitar_alta(correo, contrasena)
        if not ok:
            return Response({"detail": detalle}, status=400)
        return Response({"detail": _MENSAJE_ALTA_ENVIADO})


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(ensure_csrf_cookie, name="dispatch")
class AltaConfirmarView(_BasePublica):
    def post(self, request):
        correo = _correo_normalizado(request.data)
        codigo = _texto(request.data, "código", "codigo")
        if not correo or not codigo:
            return Response(
                {"detail": "El código no es válido o ya expiró. Solicite uno nuevo."},
                status=403,
            )
        ok, detalle = codigos.confirmar_alta(correo, codigo)
        if not ok:
            return Response(
                {
                    "detail": detalle
                    or "El código no es válido o ya expiró. Solicite uno nuevo.",
                },
                status=403,
            )
        return Response({"detail": _MENSAJE_ALTA_LISTA})


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(ensure_csrf_cookie, name="dispatch")
class OlvidoSolicitarView(_BasePublica):
    def post(self, request):
        correo = _correo_normalizado(request.data)
        if correo:
            codigos.solicitar_olvido(correo)
        return Response({"detail": _MENSAJE_OLVIDO_ENVIADO})


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(ensure_csrf_cookie, name="dispatch")
class OlvidoRestablecerView(_BasePublica):
    def post(self, request):
        correo = _correo_normalizado(request.data)
        codigo = _texto(request.data, "código", "codigo")
        contrasena = _contrasena(request.data)
        if not correo or not codigo or not contrasena:
            return Response(
                {"detail": "El código no es válido o ya expiró. Solicite uno nuevo."},
                status=403,
            )
        ok, detalle = codigos.restablecer_olvido(correo, codigo, contrasena)
        if not ok:
            return Response(
                {
                    "detail": detalle
                    or "El código no es válido o ya expiró. Solicite uno nuevo.",
                },
                status=403,
            )
        return Response({"detail": _MENSAJE_OLVIDO_LISTO})
