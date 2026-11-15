"""Configuración Django para Cody (scaffold local)."""
import sys
from pathlib import Path

import os

BASE_DIR = Path(__file__).resolve().parent.parent


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_list(name: str, default: str) -> list[str]:
    raw = os.environ.get(name, default)
    return [part.strip() for part in raw.split(",") if part.strip()]


SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "inseguro-solo-desarrollo-cambie-en-env",
)
DEBUG = _env_bool("DEBUG", True)
ALLOWED_HOSTS = _env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "config",
    "ambito",
    "sesion",
    "movimientos",
    "webhooks",
    "pey",
    "integracion",
    "ventas",
    "pedidos",
    "canales",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "ambito.middleware.AmbitoComercioMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "sesion.middleware.CierraApiSinSesionMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "cody"),
        "USER": os.environ.get("POSTGRES_USER", "cody"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "cody_local_dev"),
        "HOST": os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        "PORT": os.environ.get("POSTGRES_PORT", "5433"),
        "CONN_MAX_AGE": 600,
        "CONN_HEALTH_CHECKS": True,
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation."
        "UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es-mx"
TIME_ZONE = "America/Mexico_City"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
FRONTEND_DIST = BASE_DIR.parent / "frontend" / "build" / "web"
LANDING_DIST = BASE_DIR.parent / "landing" / "dist"

if DEBUG:
    STORAGES = {
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
else:
    STORAGES = {
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
        },
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Vacío: POST /api/webhooks/pey/ rechaza todo con 401. No hay modo sin firma.
PEY_WEBHOOK_SECRET = os.environ.get("PEY_WEBHOOK_SECRET", "")
# Vacío: el adaptador de producción no llama a pey y responde CONFIGURACION.
PEY_API_KEY = os.environ.get("PEY_API_KEY", "")
# Vacío: obtener_puerto() elige desarrollo si DEBUG, y producción si no.
PEY_ADAPTADOR = os.environ.get("PEY_ADAPTADOR", "")
PEY_BASE_URL = "https://api.pey.mx"

CODY_ROL = os.environ.get("CODY_ROL", "web")

DEMO_PEY_BANK_ACCOUNT_ID = os.environ.get("DEMO_PEY_BANK_ACCOUNT_ID", "")
NUCLEO_ADAPTADOR = os.environ.get("NUCLEO_ADAPTADOR", "")
NUCLEO_STUB_PERMITIDO = DEBUG or "test" in sys.argv
PEDIDOS_COBRO_HABILITADO = _env_bool("PEDIDOS_COBRO_HABILITADO", False)
PEDIDOS_LECTOR_PROCEDENCIA = "canales.lector.LectorProcedenciaCanal"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
}

SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = False

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

_EMAIL_HOST = os.environ.get("EMAIL_HOST", "mail.asware.com.mx")
_EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "465"))
_EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "transfiereme@asware.com.mx")
_EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
_EMAIL_USE_SSL = _env_bool("EMAIL_USE_SSL", True)
_EMAIL_USE_TLS = _env_bool("EMAIL_USE_TLS", False)
_DEFAULT_FROM = os.environ.get("DEFAULT_FROM_EMAIL", _EMAIL_HOST_USER)
_EMAIL_BACKEND_DEFAULT = "django.core.mail.backends.smtp.EmailBackend"

EMAIL_HOST = _EMAIL_HOST
EMAIL_PORT = _EMAIL_PORT
EMAIL_HOST_USER = _EMAIL_HOST_USER
EMAIL_HOST_PASSWORD = _EMAIL_HOST_PASSWORD
EMAIL_USE_SSL = _EMAIL_USE_SSL
EMAIL_USE_TLS = _EMAIL_USE_TLS
DEFAULT_FROM_EMAIL = _DEFAULT_FROM

if "test" in sys.argv:
    EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
elif DEBUG and not _EMAIL_HOST_PASSWORD.strip():
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
else:
    EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", _EMAIL_BACKEND_DEFAULT)

WAHA_BASE_URL = os.environ.get("WAHA_BASE_URL", "http://127.0.0.1:3004")
WAHA_API_KEY = os.environ.get("WAHA_API_KEY", "")
WAHA_WEBHOOK_SECRET = os.environ.get("WAHA_WEBHOOK_SECRET", "")
WAHA_INSTANCIA = os.environ.get("WAHA_INSTANCIA", "").strip() or "waha"
CANAL_TRANSPORTE = "canales.waha.AdaptadorWaha"

STT_HABILITADO = os.environ.get("STT_HABILITADO", "0") == "1"
AGENTE_PEDIDOS_API_KEY = os.environ.get("AGENTE_PEDIDOS_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
AGENTE_PEDIDOS_MODELO = os.environ.get("AGENTE_PEDIDOS_MODELO", "gpt-4.1-mini")
AGENTE_PEDIDOS_TIMEOUT_S = min(45, max(1, int(os.environ.get("AGENTE_PEDIDOS_TIMEOUT_S", "25"))))
STT_MODELO = os.environ.get("STT_MODELO", "small")
STT_CPU_THREADS = int(os.environ.get("STT_CPU_THREADS", "2"))
STT_PRESUPUESTO_S = 45
WHATSAPP_AUDIO_MAX_BYTES = 5_000_000
WHATSAPP_AUDIO_MAX_SEGUNDOS = 90
