# Variables de entorno

Este documento describe **nombres y uso**, sin valores reales. Las secretas no deben subirse al repositorio.

## Desarrollo local (scaffold MR 1)

| Variable | Secreta | Dónde vive | Para qué |
| --- | --- | --- | --- |
| `POSTGRES_DB` | No | `backend/.env` | Nombre de la base en Docker |
| `POSTGRES_USER` | No | `backend/.env` | Usuario de Postgres local |
| `POSTGRES_PASSWORD` | Sí (baja sensibilidad local) | `backend/.env` | Contraseña de Postgres local |
| `POSTGRES_HOST` | No | `backend/.env` | Host (normalmente `127.0.0.1`) |
| `POSTGRES_PORT` | No | `backend/.env` | Puerto publicado por compose (`5433`) |
| `DJANGO_SECRET_KEY` | Sí | `backend/.env` | Firmas y sesión de Django |
| `DEBUG` | No | `backend/.env` | `True` en local |
| `ALLOWED_HOSTS` | No | `backend/.env` | `localhost`, `127.0.0.1` |
| `PEY_ADAPTADOR` | No | `backend/.env` | `desarrollo` o `produccion`. Vacío: `desarrollo` si `DEBUG`, si no `produccion`. No arranca en `desarrollo` si `DEBUG=False` o si `PEY_API_KEY` tiene valor |
| `EMAIL_HOST` | No | `backend/.env` | Servidor SMTP (p. ej. `mail.asware.com.mx`) |
| `EMAIL_PORT` | No | `backend/.env` | Puerto SMTP (p. ej. `465` con SSL implícito) |
| `EMAIL_HOST_USER` | No | `backend/.env` | Usuario SMTP |
| `EMAIL_HOST_PASSWORD` | Sí | `backend/.env` | Contraseña del buzón. Vacía en local con `DEBUG`: correo a consola |
| `EMAIL_USE_SSL` | No | `backend/.env` | `True` con puerto 465 |
| `EMAIL_USE_TLS` | No | `backend/.env` | `False` con puerto 465 |
| `DEFAULT_FROM_EMAIL` | No | `backend/.env` | Remitente visible (mismo buzón que el usuario SMTP) |
| `EMAIL_BACKEND` | No | `backend/.env` | Backend Django de correo; por defecto SMTP si hay contraseña |

Plantilla: `.env.example` (también en `backend/.env.example`). `scripts/dev-start.sh` carga `backend/.env` si existe y no exige variables de pey.

## GitLab CI

Cree cada variable en **Settings → CI/CD → Variables**. No ponga valores en `.gitlab-ci.yml`. El inventario del 2026-11-14 encontró `master` protegida y `test` sin protección ni variables `TEST_*` de proyecto o grupo. `deploy:test` queda deshabilitado hasta disponer de recursos propios. Las variables `PROD_*` existentes tienen ámbito `*`; se debe pasar al ámbito `production` durante la preparación operativa, sin mostrar ni rotar valores en este cambio. Los merge requests actuales no reciben estas variables ni ejecutan CI.

### Archivo de la app

`PROD_ENV_FILE` y `TEST_ENV_FILE` son tipo **File**, protegidas. Ahí va el `.env` completo de Django, secretos incluidos. Plantilla: [ci-env-file.ejemplo](ci-env-file.ejemplo).

| Clave en el archivo | Secreta | Para qué |
| --- | --- | --- |
| `POSTGRES_DB` | No | Nombre de la base |
| `POSTGRES_USER` | No | Usuario de Postgres |
| `POSTGRES_PASSWORD` | Sí | Contraseña de Postgres |
| `POSTGRES_HOST` | No | Host de Postgres de la app |
| `POSTGRES_PORT` | No | Puerto de Postgres de la app |
| `DJANGO_SECRET_KEY` | Sí | Firmas y sesión |
| `DEBUG` | No | `False` fuera de la máquina local |
| `ALLOWED_HOSTS` | No | Dominios del despliegue |
| `WEBHOOK_BASE_URL` | No (URL pública) | Avisos; en producción `https://transfiereme.asware.com.mx` |
| `PEY_API_KEY` | Sí | Bearer contra `https://api.pey.mx` |
| `PEY_WEBHOOK_SECRET` | Sí | Firma Standard Webhooks (`whsec_...`) de `POST /api/webhooks/pey/`. Vacío: la ruta rechaza todo con 401 |
| `PEY_ADAPTADOR` | No | En producción: `produccion`. Vacío con `DEBUG=False` también elige producción. `desarrollo` exige `DEBUG` y `PEY_API_KEY` vacía. `registrar_cuenta_pey` solo corre en `produccion`. `diagnostico_pey` dice si hay llave y secreto, sin imprimirlos |
| `EMAIL_HOST` | No | Servidor SMTP |
| `EMAIL_PORT` | No | Puerto SMTP |
| `EMAIL_HOST_USER` | No | Usuario SMTP |
| `EMAIL_HOST_PASSWORD` | Sí | Contraseña del buzón (rellenar en CI File) |
| `EMAIL_USE_SSL` | No | `True` / `False` |
| `EMAIL_USE_TLS` | No | `True` / `False` |
| `DEFAULT_FROM_EMAIL` | No | Remitente |
| `EMAIL_BACKEND` | No | Backend Django (SMTP en despliegue) |

Esas cinco secretas (`POSTGRES_PASSWORD`, `DJANGO_SECRET_KEY`, `PEY_API_KEY`, `PEY_WEBHOOK_SECRET`, `EMAIL_HOST_PASSWORD`) no se repiten como variables sueltas. `scripts/ci-install-env.sh` copia el archivo a `backend/.env` con modo `600` y no imprime su contenido.

### Deploy

Estas no van en el `.env`. El job las usa para entrar al servidor; si vivieran en el archivo, la llave privada se instalaría junto a Django.

| Variable de CI | Tipo | Ámbito | Rama |
| --- | --- | --- | --- |
| `PROD_DEPLOY_HOST` | Variable, protegida | `production` | `master` |
| `PROD_DEPLOY_USER` | Variable, protegida | `production` | `master` |
| `PROD_DEPLOY_PORT` | Variable, protegida | `production` | `master` |
| `PROD_DEPLOY_PATH` | Variable, protegida | `production` | `master` |
| `PROD_SSH_PRIVATE_KEY_V2` | Variable, protegida y oculta, valor en base64 | `production` | `master` |

`DEPLOY_HOST` es el servidor, `DEPLOY_USER` quien entra por SSH, `DEPLOY_PORT` el puerto SSH. El camino nuevo exige `PROD_DEPLOY_PATH=/opt/codi/prod` exactamente y conserva host `100.120.112.112`, puerto `30022`. La clave pública del host está fijada en `deploy/known_hosts.prod`; un cambio de identidad SSH detiene el job hasta verificarlo y actualizar ese archivo. `PROD_SSH_PRIVATE_KEY_V2` es la llave privada nueva en base64 de una sola línea (`base64 -w 0`); el job la decodifica a un archivo temporal y no la copia al `.env`. La antigua `PROD_SSH_PRIVATE_KEY` queda revocada para que los jobs de commits anteriores no puedan entrar al VPS. El script rechaza el archivo de la app si trae claves de deploy o un bloque `PRIVATE KEY`.

El pipeline se crea en push o lanzamiento manual a `master` o `test`. `deploy:test` está bloqueado y `deploy:prod` requiere lanzamiento manual. El deploy productivo exige que la migración a `/opt/codi/prod` ya haya sido aceptada: valida la ruta, la unit activa y PostgreSQL antes de sincronizar; mantiene un `flock` remoto durante rsync y el reinicio; no crea PostgreSQL. Instala dependencias, respalda y aplica migraciones y prepara estáticos antes de detener `cody`. Al reiniciar comprueba `/api/salud/`. `codi-postgres` debe seguir sano en `127.0.0.1:5435`, con datos en `/var/lib/codi/postgres`; el entorno debe traer `POSTGRES_HOST=127.0.0.1` o `localhost` y `POSTGRES_PORT=5435`. El usuario de deploy necesita acceso Docker y `sudo` sin contraseña para `systemctl` e `install`. `PROD_PYTHON` es opcional (por defecto `/opt/uv-python/cpython-3.12.14-linux-x86_64-gnu/bin/python3.12`). `deploy/cody.service.in` fija `GUNICORN_BIND=0.0.0.0:8000`; un `GUNICORN_BIND` en `.env` lo sustituye. `DEBUG` debe ser `False`. El bloqueo nuevo no detiene scripts de commits antiguos: durante el corte se revoca su acceso SSH efectivo y se comprueba que no quedan jobs activos antes de crear hijos en `/opt/codi`.

El Postgres del job `backend:test` sigue con una contraseña efímera en el YAML, distinta de la del archivo. Las plantillas `.env.example` traen `PEY_ADAPTADOR=desarrollo`. Ese adaptador no usa `PEY_API_KEY`, `PEY_WEBHOOK_SECRET` ni `https://api.pey.mx`. `obtener_puerto()` lo rechaza cuando `PEY_API_KEY` tiene valor, para que un `DEBUG` encendido por error no conviva con la llave real.

## Fase 1: pedidos y canal WhatsApp

El demo se decide por comercio. Django usa `NUCLEO_ADAPTADOR` y
`PEDIDOS_COBRO_HABILITADO`, que admite `true` o `false`; opcionalmente,
`DEMO_PEY_BANK_ACCOUNT_ID` identifica el destino de la cuenta demo. Estas
variables no modifican el mecanismo de deploy.

Para WhatsApp, Django usa `WAHA_BASE_URL` (por defecto
`http://127.0.0.1:3004`), `WAHA_API_KEY`, `WAHA_WEBHOOK_SECRET` y
`WAHA_INSTANCIA` (por defecto `waha`, identificador lógico). Las claves API
y HMAC son secretas distintas. `WEBHOOK_BASE_URL` permanece para pey y su
callback, con secreto independiente. `WAHA_IMAGE` y `WHATSAPP_HOOK_*` no
pertenecen al env de la app ni a su CI.

WAHA vive en `deploy/waha-prod/` y se instala a mano mediante
`scripts/infra/instalar-waha-prod.sh`, con configuración instalada en
`/opt/codi/waha-prod` y proyecto `codi-waha-prod`. El deploy Django no ejecuta
ese instalador ni gestiona contenedores. Configurar el callback público
`/api/webhooks/waha/`, evento `message` y HMAC SHA-512 compatible con Django
es una operación independiente, al igual que vincular el número.

El remoto instala `requirements-canal.txt`, que incluye los requisitos de
la app. Antes de detener servicios prepara dependencias, checks, estáticos,
las dos units y `backend/.env.canal` filtrado, modo 600, sin llaves pey,
secretos de firma ni contraseña SMTP. Conserva URL/API/instancia WAHA y
configuración Django/BD/modo. El File común completo sigue en `backend/.env`.
Rsync protege ambos env, el venv y staticfiles.

`cody-canal.service` ejecuta `manage.py procesar_canal` desde
`/opt/codi/prod/backend`, con el mismo usuario y venv de la app. Tras reiniciar
web y comprobar salud HTTP 200, reinicia canal y exige un latido posterior
al reinicio más unit activa. Solo entonces habilita la unit canal y acepta
el deploy. Si falla el arranque, restaura units/env previos, vuelve a arrancar
web y recupera el estado previo del canal, incluida su primera instalación.
Esta recuperación no revierte código ni dependencias sincronizadas.

En cada deploy normal se crea un respaldo `pg_dump -Fc` en
`~/respaldos/codi` del usuario de deploy y se conservan los 10 más recientes.
Después se ejecutan `migrate --plan`, `migrate --noinput` y
`migrate --check --noinput`, antes de detener servicios. Si falla cualquiera
de estos pasos, se aborta el deploy sin reiniciar servicios. Las migraciones
corren mientras la versión anterior sigue sirviendo: deben ser compatibles
hacia atrás (aditivas); los cambios destructivos requieren un procedimiento
aparte. Un fallo posterior a migrar puede dejar las migraciones aplicadas con
los servicios anteriores activos; se debe revisar y reintentar, pues la base no
se revierte y el respaldo no se restaura automáticamente. Se necesita espacio
en disco para un respaldo adicional antes de aplicar la retención. El `pg_dump`
alarga el tiempo que se mantiene el bloqueo del deploy. El mecanismo de exclusión
sigue siendo el flock remoto sostenido por SSH y `guardian_alive`.
