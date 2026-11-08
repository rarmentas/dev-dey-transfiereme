from django.contrib.auth import authenticate, get_user_model, login, logout
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ambito.models import Membresia
from sesion.authentication import SessionAuthenticationSinCsrf

User = get_user_model()

_MENSAJE_CREDENCIALES = "Revise el correo y la contraseña."


def _correo_y_contrasena(data) -> tuple[str, str]:
    correo_raw = data.get("correo") or data.get("usuario") or data.get("username")
    contrasena = data.get("contraseña") or data.get("contrasena") or data.get("password")
    if not isinstance(correo_raw, str):
        correo_raw = ""
    correo = correo_raw.strip()
    if contrasena is None:
        contrasena = ""
    return correo, contrasena


def _autenticar_por_correo(request, correo: str, contrasena: str):
    user = authenticate(request, username=correo, password=contrasena)
    if user is None and correo != correo.lower():
        user = authenticate(request, username=correo.lower(), password=contrasena)
    if user is not None:
        return user
    candidatos = User.objects.filter(email__iexact=correo)[:2]
    if candidatos.count() != 1:
        return None
    return authenticate(request, username=candidatos[0].username, password=contrasena)


def _comercio_en_request(request) -> dict | None:
    comercio = getattr(request, "comercio", None)
    if comercio is None:
        try:
            comercio = request.user.membresia.comercio
        except Membresia.DoesNotExist:
            return None
    return {"id": comercio.pk, "nombre": comercio.nombre}


def _perfil_usuario(request) -> dict:
    user = request.user
    return {
        "usuario": user.username,
        "correo": user.email or "",
        "nombre": user.first_name or "",
        "apellidos": user.last_name or "",
        "comercio": _comercio_en_request(request),
    }


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(ensure_csrf_cookie, name="dispatch")
class EntrarSesionView(APIView):
    """Inicia sesión Django; deja cookies sessionid y csrftoken."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        correo, contrasena = _correo_y_contrasena(request.data)
        if not correo or not contrasena:
            return Response({"detail": _MENSAJE_CREDENCIALES}, status=403)
        user = _autenticar_por_correo(request, correo, contrasena)
        if user is None:
            return Response({"detail": _MENSAJE_CREDENCIALES}, status=403)
        login(request, user)
        return Response({"usuario": user.username})


class EstadoSesionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(_perfil_usuario(request))


class SalirSesionView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [SessionAuthenticationSinCsrf]

    def post(self, request):
        logout(request)
        return Response({})
