# Stack tecnológico

Cody usa la misma plataforma que `dent-intec`. Las versiones de este documento salen de los manifiestos de ese repositorio. El código de Cody todavía no está generado: esto fija con qué se va a construir.

## Capas

| Capa | Elección | Versión fijada |
|---|---|---|
| App | Flutter, web y Android | SDK de Flutter **3.47.8** (imagen de CI `ghcr.io/gmeligio/flutter-web:3.47.8`); Dart `sdk: ^3.13.7` |
| API | Django + Django REST Framework | Django **6.1.2**, DRF **3.18.3** |
| Lenguaje del API | Python | **3.12** (el venv no puede ser 3.14) |
| Base de datos | PostgreSQL | **17** (`postgres:17` en Docker) |
| Servidor de aplicación | Gunicorn + WhiteNoise | Gunicorn **26.2.0**, WhiteNoise **6.12.0** |
| Cliente HTTP | Dio, con cookie de sesión y CSRF | Dio **5.11.1**, `cookie_jar` **4.0.8**, `dio_cookie_manager` **3.2.0** |
| Estado y rutas | Riverpod y GoRouter | `flutter_riverpod` **3.4.3**, `go_router` **18.1.1** |
| Asistente | LangGraph sobre LangChain | `langgraph` **1.0.3**, `langchain-core` **1.0.2**, `langchain-openai` **1.0.2**, `langchain-ollama` **1.0.0** |
| Pruebas de UI | `flutter_test` + `flutter_lints` | `flutter_lints` **^6.0.0** |
| Zona horaria | `America/Mexico_City`, idioma `es` | — |

El mismo proceso de Django sirve `/api/` y, en el build de release, el estático de Flutter. En web, la app y el API comparten origen: la cookie de sesión viaja sola y no hace falta un token aparte.

## Forma del repositorio

Cuando se genere el código, el árbol sigue el de la referencia:

```text
backend/          Django (config/, apps de dominio, manage.py, requirements.txt)
backend/.venv/    Python 3.12; no se commitea
frontend/         Flutter (lib/core, lib/features, test, web, android)
frontend/build/web/   artefacto que Django sirve
scripts/          upgrade.sh, dev-start.sh, build de Android
deploy/           units de systemd
compose.yaml      Postgres local
.gitlab-ci.yml    build web + deploy
```

En el frontend, `lib/core/` concentra tema, cliente HTTP y sesión. Cada feature vive en `lib/features/<nombre>/` con `data/` (modelos y repositorio) y `presentation/` (pantallas). Las rutas se declaran en `lib/main.dart` con GoRouter. El estado de pantalla va con Riverpod.

En el backend, `config/` tiene settings, URLs y middleware. Cada app de dominio tiene `models.py`, `views.py`, `urls.py`, `migrations/` y `tests/`.

## Frontend

Dependencias de la app de referencia que forman el cliente:

| Paquete | Versión | Para qué |
|---|---|---|
| `dio` | 5.11.1 | HTTP hacia el mismo origen |
| `cookie_jar` / `dio_cookie_manager` | 4.0.8 / 3.2.0 | Cookie de sesión en Android (en web la maneja el navegador) |
| `flutter_riverpod` | 3.4.3 | Estado |
| `go_router` | 18.1.1 | Rutas |
| `intl` | ^0.20.3 | Fechas y montos |
| `material_ui` | 1.8.0 | Componentes Material |
| `path_provider` | 2.1.5 | Rutas de archivos en el dispositivo |
| `web` | 1.1.2 | APIs del navegador |
| `cross_file` | ^0.3.4 | Archivos entre plataformas |
| `url_launcher` | 6.3.3 | Abrir enlaces |
| `share_plus` | 10.1.4 | Compartir |
| `qr_flutter` | ^4.1.0 | QR (en Cody, el cobro CoDi) |
| `record` / `audioplayers` | 6.0.0 / 6.4.0 | Grabar y reproducir si se prende la voz |
| `clock` | 1.1.3 | Reloj inyectable en pruebas |

Lint: `analysis_options.yaml` incluye `package:flutter_lints/flutter.yaml` y excluye `build/**`, `web/**` y `android/**`. El análisis es `flutter analyze`.

Android: `minSdk` 21, iconos con `flutter_launcher_icons` **^0.14.4**. iOS no entra. El build web de release usa `--base-href /app/` cuando hay una landing en `/`; si Cody no tiene landing, el estático puede vivir en `/`.

El cliente arma Dio con `Accept: application/json`, `connectTimeout` de 10 s y `sendTimeout` de 30 s. El `receiveTimeout` no tiene tope global porque una vuelta del modelo puede tardar; cada llamada acotada lo fija ella. En web, sin `API_BASE_URL`, la base es el origen de la página. Un `--dart-define=API_BASE_URL=...` lo pisa (útil en Android).

## Backend

`backend/requirements.txt` de la referencia:

```text
Django==6.1.2
djangorestframework==3.18.3
psycopg[binary]==3.3.6
gunicorn==26.2.0
whitenoise==6.12.0
langgraph==1.0.3
langchain-core==1.0.2
langchain-openai==1.0.2
langchain-ollama==1.0.0
phonenumbers==9.0.42
cryptography==50.0.2
boto3==1.43.123
lxml==6.1.3
reportlab==5.1.0
requests==2.34.2
```

`phonenumbers`, `boto3`, `lxml` y `reportlab` están en dent-intec por WhatsApp, R2 y CFDI. Cody los incluye solo si una feature los necesita. El núcleo que sí entra desde el primer scaffold es Django, DRF, `psycopg`, Gunicorn, WhiteNoise, LangChain/LangGraph y `requests`. `cryptography` entra si hay un secreto que cifrar en reposo.

Apps de Django que sí se copian como base: `admin`, `auth`, `contenttypes`, `sessions`, `messages`, `staticfiles`, `postgres` y `rest_framework`.

Middleware, en este orden:

1. `SecurityMiddleware`
2. `WhiteNoiseMiddleware`
3. `SessionMiddleware`
4. `CommonMiddleware`
5. `CsrfViewMiddleware`
6. `AuthenticationMiddleware`
7. Middleware de ámbito de la cuenta (en dent-intec, la clínica; en Cody, el comercio)
8. `MessageMiddleware`
9. `XFrameOptionsMiddleware`
10. Middleware que cierra `/api/` sin sesión

DRF:

- Autenticación: `SessionAuthentication` (no JWT).
- Permiso por defecto: `IsAuthenticated`.
- Renderer: solo JSON.

Cookies: `SESSION_COOKIE_SAMESITE` y `CSRF_COOKIE_SAMESITE` en `Lax`. `CSRF_COOKIE_HTTPONLY` es `False` para que el cliente lea el token y lo mande en el encabezado. Fuera de `DEBUG`, `SESSION_COOKIE_SECURE` y `CSRF_COOKIE_SECURE` van en verdadero, y el proxy se honra con `SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')`.

Conexión a Postgres: `CONN_MAX_AGE` 600 y `CONN_HEALTH_CHECKS`. Tope de subida en memoria: 5 MB. `USE_TZ = True`. `DEFAULT_AUTO_FIELD` es `BigAutoField`.

Archivos estáticos: en `DEBUG`, `StaticFilesStorage`; si no, `whitenoise.storage.CompressedStaticFilesStorage`. `STATIC_ROOT` apunta a `backend/staticfiles/` (no se commitea). `FRONTEND_DIST` apunta a `frontend/build/web`.

No hay linter de Python configurado. La revisión rápida del backend es `manage.py check`. Las pruebas son `manage.py test <app>.tests.<módulo>` y necesitan Postgres.

## Sesión

La sesión es la de Django.

- Entrar: `POST /api/sesion/entrar/`
- Salir: `POST /api/sesion/salir/`
- Estado: `GET /api/sesion/estado/`

Un middleware responde 403 a `GET` y `POST` bajo `/api/` si no hay usuario. Quedan fuera el propio inicio de sesión, el estado, el alta (si se publica) y los webhooks. El cliente, al perder la sesión, abre el login.

El ámbito (clínica allá, comercio aquí) lo pone el servidor a partir de la membresía del usuario. El cliente no lo elige en el cuerpo del request. Un recurso de otra cuenta responde 404.

## Asistente

LangGraph corre dentro del request de Gunicorn. No hay worker aparte para el chat.

`LLM_SERVER` elige el proveedor:

| Valor | Variables |
|---|---|
| `ollama` (default de la referencia) | `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `OLLAMA_KEEP_ALIVE`, `OLLAMA_NUM_CTX` |
| `openai` | `OPENAI_API_KEY`, `OPENAI_MODEL` (default de la referencia `gpt-4.1-mini`), `OPENAI_REASONING_EFFORT` (default `none`), `OPENAI_MAX_TOKENS` |

El modelo no arma llamadas externas a mano: el grafo expone herramientas y el servidor las ejecuta. En Cody esas herramientas hablan con la API de pey (`/codi/qr`, `/codi/pn`, links de pago). Los webhooks `codi.qr.payment_received` y `codi.pn.payment_received` entran por una ruta pública, igual que el webhook de la referencia: responden pronto y el trabajo pesado no bloquea al emisor si hace falta una cola.

## Voz (opcional)

Mismo mecanismo que la referencia, en `requirements-voz.txt`, instalado solo si se prende:

| Pieza | Pin | Notas |
|---|---|---|
| STT | `faster-whisper==1.1.1`, `numpy==2.2.4` | CPU. Exige **ffmpeg** en `PATH` y Python 3.12 (`ctranslate2` no tiene wheel estable para 3.14) |
| TTS Kokoro | `kokoro-onnx>=0.4.9` | Exige **espeak-ng** y los pesos en disco |
| TTS Piper | binario y voz en el host | El deploy no pisa ese directorio |

`STT_HABILITADO=1` abre el endpoint de audio. `TTS_HABILITADO=1` más `TTS_MOTOR` (`piper` o `kokoro`) prende la síntesis. En el hackatón la voz sigue siendo opcional: el cobro tiene que poder armarse por texto.

## Datos y secretos

Postgres 17 en Docker. En local el compose de la referencia publica **5433** en el host para no chocar con un Postgres del sistema. Volumen nombrado. Healthcheck con `pg_isready`.

Variables de conexión: `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`.

El `.env` no se commitea. En el VPS de la referencia lo instala el pipeline desde una variable File de GitLab. Cody sigue esa regla en cuanto haya remoto y despliegue.

## Desarrollo local

El venv y el SDK de Flutter los crea `scripts/upgrade.sh` (Python 3.12 vía `uv` o `python3.12`; Flutter en `.tooling/flutter`).

`scripts/dev-start.sh` deja tres procesos y un solo origen en el navegador:

| Proceso | Puerto en la referencia |
|---|---|
| Proxy que une API y recarga de Flutter | 8000 (el que abre el navegador) |
| Django | 8001 |
| Flutter web en caliente | 9100 |

Postgres: `docker compose up -d postgres`.

Pruebas acotadas a lo que se tocó, no la suite completa:

- Backend: `cd backend && .venv/bin/python manage.py test <modulo>`
- Frontend: `cd frontend && flutter test test/<archivo>_test.dart`

## Despliegue

Patrón de la referencia, para cuando Cody salga del hackatón local:

- CI en GitLab, runners con tag `docker`. Ramas que despliegan: una de trabajo (en la referencia, `demo`) y `master`.
- Job de build: imagen Flutter 3.47.8, `flutter pub get`, `flutter test`, `flutter build web --release`.
- Job de deploy: imagen `alpine:3.22`, `bash`, `openssh-client`, `rsync`. Copia el árbol, instala el `.env`, `pip install`, `migrate`, `collectstatic`, reinicia systemd y espera HTTP 200.
- El proceso de aplicación es una unit systemd: usuario propio, `EnvironmentFile`, Gunicorn con `--bind`, `--workers` y `--timeout` por variables, logs a stdout (journald), `Restart=always`, `NoNewPrivileges`, `ProtectSystem=strict`.
- Tareas periódicas y colas van en units aparte (`*.service` + `*.timer`), no dentro del request.

Cody en el día del hackatón puede correr solo en local. El documento deja el patrón para no inventar otro servidor ni otro CI después.
