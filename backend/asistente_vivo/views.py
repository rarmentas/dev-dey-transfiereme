"""Entrega tokens Gemini Live de un solo uso sin exponer la API key."""
from datetime import datetime, timedelta, timezone

from django.conf import settings
from django.core.cache import cache
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ambito.exceptions import SinAmbitoError
from ambito.scope import requerir_comercio

INSTRUCCIONES = (
    "Eres el asistente de Transfiéreme para un tendero mexicano. Habla siempre "
    "en español de México, con respuestas breves, claras y amables. Solo puedes "
    "consultar ventas de hoy, pedidos pendientes y el detalle de un pedido. "
    "Usa las herramientas para datos actuales. Nunca crees cobros, publiques "
    "cotizaciones, aceptes pedidos ni cambies cuentas; si te lo piden, explica "
    "amablemente que por seguridad solo puedes consultar información."
)

HERRAMIENTAS = [{"function_declarations": [
    {"name": "resumen_ventas_hoy", "description": "Consulta el resumen de ventas cobradas hoy."},
    {"name": "pedidos_pendientes", "description": "Lista los pedidos pendientes de revisar o cotizar."},
    {"name": "detalle_pedido", "description": "Obtiene el detalle de un pedido por su número.", "parameters": {"type": "OBJECT", "properties": {"numero": {"type": "STRING", "description": "Número visible del pedido."}}, "required": ["numero"]}},
]}]


def configuracion_live() -> dict:
    """Configuración bloqueada dentro del token; no depende del navegador."""
    return {
        "response_modalities": ["AUDIO"],
        "system_instruction": {"parts": [{"text": INSTRUCCIONES}]},
        "tools": HERRAMIENTAS,
        "input_audio_transcription": {},
        "output_audio_transcription": {},
        "speech_config": {"voice_config": {"prebuilt_voice_config": {"voice_name": "Kore"}}},
    }


def crear_cliente():
    """Importación diferida: la app puede arrancar sin la integración instalada."""
    from google import genai
    return genai.Client(api_key=settings.GEMINI_API_KEY, http_options={"api_version": "v1alpha"})


class TokenAsistenteVivoView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not settings.GEMINI_API_KEY.strip():
            return Response({"codigo": "ASISTENTE_NO_CONFIGURADO", "mensaje": "El asistente no está configurado."}, status=503)
        try:
            requerir_comercio(request)
        except SinAmbitoError:
            return Response({"codigo": "PERMISO_DENEGADO", "mensaje": "No tienes un comercio asignado."}, status=403)

        user_key = f"asistente-vivo:activo:{request.user.pk}"
        hour_key = f"asistente-vivo:hora:{request.user.pk}"
        if cache.get(user_key):
            return Response({"codigo": "SESION_ACTIVA", "mensaje": "Ya tienes una sesión de asistente activa."}, status=429)
        usos = cache.get(hour_key, 0)
        if usos >= settings.GEMINI_LIVE_MAX_SESIONES_HORA:
            return Response({"codigo": "LIMITE_SESIONES", "mensaje": "Alcanzaste el límite de sesiones por hora."}, status=429)

        # Reserva antes de pedir el token para evitar carreras entre pestañas.
        if not cache.add(user_key, True, timeout=90):
            return Response({"codigo": "SESION_ACTIVA", "mensaje": "Ya tienes una sesión de asistente activa."}, status=429)
        try:
            ahora = datetime.now(timezone.utc)
            cliente = crear_cliente()
            token = cliente.auth_tokens.create(config={
                "uses": 1,
                "expire_time": ahora + timedelta(minutes=15),
                "new_session_expire_time": ahora + timedelta(minutes=1),
                "live_connect_constraints": {
                    "model": settings.GEMINI_LIVE_MODELO,
                    "config": configuracion_live(),
                },
            })
        except Exception:
            cache.delete(user_key)
            return Response({"codigo": "ASISTENTE_NO_DISPONIBLE", "mensaje": "No pudimos iniciar el asistente. Intenta más tarde."}, status=503)

        cache.set(hour_key, usos + 1, timeout=60 * 60)
        return Response({"token": token.name, "modelo": settings.GEMINI_LIVE_MODELO, "expira_en_segundos": 60})
