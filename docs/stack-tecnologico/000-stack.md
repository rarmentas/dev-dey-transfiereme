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
| Cobros | API de pey | `https://api.pey.mx`, contrato en [docs.pey.mx](https://docs.pey.mx) |
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
| `clock` | 1.1.3 | Reloj inyectable en pruebas |

Lint: `analysis_options.yaml` incluye `package:flutter_lints/flutter.yaml` y excluye `build/**`, `web/**` y `android/**`. El análisis es `flutter analyze`.

Android: `minSdk` 21, iconos con `flutter_launcher_icons` **^0.14.4**. iOS no entra. El build web de release usa `--base-href /app/` cuando hay una landing en `/`; si Cody no tiene landing, el estático puede vivir en `/`.

El cliente arma Dio con `Accept: application/json`, `connectTimeout` de 10 s y `sendTimeout` de 30 s. El `receiveTimeout` es de 30 s; la espera del pago no usa una conexión larga sino consultas cortas repetidas. En web, sin `API_BASE_URL`, la base es el origen de la página. Un `--dart-define=API_BASE_URL=...` lo pisa (útil en Android).

## Backend

`backend/requirements.txt` de la referencia:

```text
Django==6.1.2
djangorestframework==3.18.3
psycopg[binary]==3.3.6
gunicorn==26.2.0
whitenoise==6.12.0
phonenumbers==9.0.42
cryptography==50.0.2
boto3==1.43.123
lxml==6.1.3
reportlab==5.1.0
requests==2.34.2
```

`phonenumbers`, `boto3`, `lxml` y `reportlab` están en dent-intec por WhatsApp, R2 y CFDI. Cody los incluye solo si una feature los necesita. El núcleo que sí entra desde el primer scaffold es Django, DRF, `psycopg`, Gunicorn, WhiteNoise y `requests`, más `standardwebhooks` para verificar la firma de los webhooks de pey (no está en la referencia; se fija la versión al instalarla). `cryptography` entra si hay un secreto que cifrar en reposo.

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

## Cobros (API de pey)

La capa de cobro habla con la API pública de pey. Autenticación: `Authorization: Bearer` con `PEY_API_KEY`. Base: `https://api.pey.mx` (producción). El índice de la documentación también menciona `https://api.dev.pey.mx` y llaves `test` en `portal.dev.mipey.mx`, pero la portada dice que el ambiente de pruebas llega "próximamente"; en el hackatón se usa producción. Contrato tomado de [docs.pey.mx](https://docs.pey.mx) y de su [openapi.json](https://docs.pey.mx/openapi.json) (versión `2026-10-20`), revisado el 7 de noviembre de 2026.

| Uso en Cody | Llamada |
|---|---|
| QR general del local y QR de una venta | `POST /codi/qr` |
| Cobro al celular del cliente | `POST /codi/pn` |
| Pago de un QR | webhook `codi.qr.payment_received` |
| Pago de una notificación | webhook `codi.pn.payment_received` |
| Respaldo del estado de una notificación | `GET /transaction/{id}` |
| Respaldo de los pagos de un QR | `GET /transaction/codi/qr/{id}` |

El NFC lo hace la app bancaria del cliente sobre ese cobro; pey no expone un endpoint de NFC.

### `POST /codi/qr`

| Campo | Tipo | Regla |
|---|---|---|
| `amount` | number, **obligatorio** | `>= 0`. **`0` deja que el pagador teclee el monto** |
| `concept` | string | Lo que ve el pagador. Sin largo máximo documentado |
| `expiration` | integer, segundos | `0` = sin expiración (default). Si se fija, mínimo **360** |
| `numRef` | string | Solo dígitos, **1 a 7** (`^[0-9]{1,7}$`). Default `"0"` |
| `generateImage` | boolean | Default `false`. Si es `true`, regresa `qrImage` en PNG base64 (más lento) |
| `bankAccountId` | string (ULID) | Cuenta `codiStatus: ACTIVE`. Sin él, abona a la cuenta ligada a la API key |
| `metadata` | object | Hasta 50 pares; llaves de hasta 40 caracteres, valores de hasta 500; todo se regresa como string |

Respuesta **201**: `id` (IDC de Banxico), `qrString` (lo que se codifica en el QR) y `qrImage` (solo con `generateImage`). Cody pinta el QR desde `qrString` con `qr_flutter`, sin pedir la imagen.

Uso en Cody:

- **QR general:** `amount: 0`, `expiration: 0`, `concept: "Transferencia"`. Se crea una vez por comercio y se guarda. La documentación no dice "QR reutilizable", pero `GET /transaction/codi/qr/{id}` lista varias transacciones por QR, así que un mismo QR recibe varios pagos. **Confirmar con un segundo pago de $0.01.**
- **QR por venta:** monto capturado, `expiration` de 360 o más, `concept` capturado o "Transferencia" si viene vacío. La **referencia del vendedor tiene que ser numérica de hasta 7 dígitos**: la pantalla la valida así.

### `POST /codi/pn`

| Campo | Tipo | Regla |
|---|---|---|
| `amount` | number, **obligatorio** | `> 0` y `<= 1,000,000`. Aquí no hay monto abierto |
| `phoneNumber` | string, **obligatorio** | 10 dígitos, sin lada de país (`^[0-9]{10}$`) |
| `concept` | string | Igual que en el QR; "Transferencia" si viene vacío |
| `expiration` | integer, segundos | Mínimo y default **360** |
| `numRef`, `bankAccountId`, `metadata` | | Mismas reglas que en el QR |

Respuesta **200**: `transactionId` (ULID, con él se sigue el pago) y `codiId` (folio de Banxico de 20 dígitos).

Errores de las dos llamadas: `400` con `{error: {message, type, requestId}}` (`INVALID_REQUEST`, `INVALID_AMOUNT`, `INVALID_PARAMETER`, `INVALID_STATE`, …), `500` y `503`. Cody guarda `requestId` para preguntarle a pey.

### Webhooks

Campos de `codi.qr.payment_received`: `type`, `amount`, `concept`, `numRef`, `datePaid` (unix, segundos), `transactionId` (ULID), `codiQrId` (IDC), `apiKeyId`, `metadata` y `bankAccountId` (solo si se mandó al crear el QR).

`codi.pn.payment_received` trae los mismos campos **sin `codiQrId`**.

Cómo se liga el pago al cobro de Cody:

| Canal | Llave |
|---|---|
| QR (general o por venta) | `codiQrId` del webhook = `id` de la respuesta de `POST /codi/qr` |
| Notificación | `transactionId` del webhook = `transactionId` de la respuesta de `POST /codi/pn` (inferido de la documentación; confirmar con el primer cobro) |

En el QR general, cada webhook crea un movimiento nuevo (un pago por `transactionId`) colgado del mismo QR. El `amount` del webhook es el monto que tecleó el cliente.

No ligar por `numRef`: la documentación lo describe como "asignado a Banxico" y el ejemplo del webhook no repite el valor del ejemplo de creación.

No hay eventos de rechazo ni de expiración. Si el cliente rechaza o el cobro vence, no llega nada: Cody marca el cobro como **vencido** cuando pasa su `expiration`.

Configuración y firma:

- La URL se registra en [portal.mipey.mx/developers](https://portal.mipey.mx/developers): engrane de la API key → webhook. **Una API key tiene un solo webhook**, así que la misma ruta recibe los dos eventos y despacha por `type`.
- Al crearlo, el portal muestra el secreto (`whsec_...`) una sola vez. Se puede rotar desde el mismo engrane. Va en `PEY_WEBHOOK_SECRET`.
- pey firma con [Standard Webhooks](https://www.standardwebhooks.com/). Se verifica con `standardwebhooks.Webhook(secret).verify(cuerpo_crudo, headers)` sobre el **cuerpo crudo**, no sobre el JSON parseado.
- `webhook-id` es la llave de idempotencia: Cody guarda cada uno y descarta repetidos.
- La política de reintentos no está documentada. El portal tiene "Webhook Logs" para ver entregas. La ruta responde 200 pronto y marca el cobro dentro de la misma transacción de base de datos.

La ruta del webhook es pública (fuera del middleware de sesión) y solo acepta peticiones con firma válida.

### Espera del pago en pantalla

La app consulta a Django cada 2 s mientras muestra un cobro. Django responde con el estado guardado (pendiente, pagado, vencido). Si el webhook no ha llegado, Django puede preguntar a pey como respaldo:

- Notificación: `GET /transaction/{transactionId}`, con `status` `PENDING` o `PAID`.
- QR: `GET /transaction/codi/qr/{id}`, hasta 20 transacciones, la más nueva primero.

No hay límite de peticiones documentado; el respaldo se usa con moderación.

### Concepto editable

El concepto que manda Cody a pey (y que ve el pagador) se guarda tal cual. Aparte, cada movimiento tiene un **concepto visible** que empieza igual ("Transferencia" si no había) y el vendedor puede cambiar, como en una app bancaria. El tablero agrupa por el concepto visible, normalizado (minúsculas, sin espacios sobrantes). El cambio no se manda a pey.

### Pruebas

Se prueba en producción con montos de **$0.01**; lo pagado no se devuelve. Para activar al momento, la documentación ofrece una cuenta de pruebas (CLABE `012180015826225713`). Una cuenta propia registrada por API tarda hasta 5 días hábiles en quedar `ACTIVE`.

### Lo que la documentación no dice

- Si un QR con `amount: 0` y `expiration: 0` acepta pagos sin límite (se infiere que sí).
- Reintentos, tiempo de espera y códigos esperados del webhook.
- Largo máximo de `concept`.
- Si `metadata` enviada regresa igual en el webhook.
- Límite de peticiones.

## Datos y secretos

Postgres 17 en Docker. En local el compose de la referencia publica **5433** en el host para no chocar con un Postgres del sistema. Volumen nombrado. Healthcheck con `pg_isready`.

Variables de conexión: `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`.

Cobro: `PEY_API_KEY` (Bearer contra `https://api.pey.mx`), `PEY_WEBHOOK_SECRET` (secreto `whsec_...` del portal) y `WEBHOOK_BASE_URL` para que pey entregue `codi.qr.payment_received` y `codi.pn.payment_received`.

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
