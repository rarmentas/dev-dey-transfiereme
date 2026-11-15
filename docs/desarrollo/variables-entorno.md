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

Cree cada variable en **Settings → CI/CD → Variables**. No ponga valores en `.gitlab-ci.yml`. Proteja las ramas `master` y `test`. El ámbito `production` solo entra al job de `master`; el ámbito `test`, solo al de la rama `test`. Los merge requests no las reciben.

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

Las siete secretas (`POSTGRES_PASSWORD`, `DJANGO_SECRET_KEY`, `PEY_API_KEY`, `PEY_WEBHOOK_SECRET`, `EMAIL_HOST_PASSWORD`, `WAHA_API_KEY`, `WAHA_WEBHOOK_SECRET`) no se repiten como variables sueltas. `scripts/ci-install-env.sh` copia el archivo a `backend/.env` con modo `600` y no imprime su contenido.

### Deploy

Estas no van en el `.env`. El job las usa para entrar al servidor; si vivieran en el archivo, la llave privada se instalaría junto a Django.

| Variable de CI | Tipo | Ámbito | Rama |
| --- | --- | --- | --- |
| `PROD_DEPLOY_HOST` | Variable, protegida | `production` | `master` |
| `PROD_DEPLOY_USER` | Variable, protegida | `production` | `master` |
| `PROD_DEPLOY_PORT` | Variable, protegida | `production` | `master` |
| `PROD_DEPLOY_PATH` | Variable, protegida | `production` | `master` |
| `PROD_SSH_PRIVATE_KEY` | Variable, protegida, valor en base64 | `production` | `master` |
| `TEST_DEPLOY_HOST` | Variable, protegida | `test` | `test` |
| `TEST_DEPLOY_USER` | Variable, protegida | `test` | `test` |
| `TEST_DEPLOY_PORT` | Variable, protegida | `test` | `test` |
| `TEST_DEPLOY_PATH` | Variable, protegida | `test` | `test` |
| `TEST_SSH_PRIVATE_KEY` | Variable, protegida, valor en base64 | `test` | `test` |

`DEPLOY_HOST` es el servidor, `DEPLOY_USER` quien entra por SSH, `DEPLOY_PORT` el puerto SSH y `DEPLOY_PATH` exactamente `/opt/codi/prod` para producción, sin barra final. `PROD_SSH_PRIVATE_KEY` y `TEST_SSH_PRIVATE_KEY` son la llave privada en base64 de una sola línea (`base64 -w 0`). El job la decodifica a un archivo temporal y no la copia al `.env`. El script rechaza el archivo de la app si trae esas claves o un bloque `PRIVATE KEY`.

El deploy de test está deshabilitado hasta aislar sus recursos. Producción utiliza
`/opt/codi/prod`, las units `cody` y `cody-canal` y el bind existente de Gunicorn.
El usuario necesita sudo sin contraseña para systemctl e install y acceso a Docker.
No necesita escritura sobre `/opt/codi`, que administra root. Operación precrea
`/opt/codi/.deploy.lock` como archivo regular persistente, sin symlink, con
lectura y escritura para la identidad de deploy (propietario, grupo o ACL). No se
borra ni se recrea mientras se usa: flock protege el inode, no el nombre. Sin ese
archivo el deploy falla antes de transferir; no se abren permisos del padre para
sortearlo. Operación puede impedir despliegues creando `/opt/codi/.maintenance`
bajo el mismo candado en modo exclusivo. El guard toma el candado exclusivo,
escribe un token y pasa a compartido; rsync, la escritura del env y
`deploy-remoto.sh` sostienen su propio flock compartido y validan ese token, así
que un deploy o mantenimiento nuevo espera a que terminen. Los jobs antiguos deben
deshabilitarse aparte. Revise los drop-ins de ambas units.

PostgreSQL `codi-postgres` del proyecto `codi`, servicio `postgres`, debe estar
operativo en `127.0.0.1:5435`; operación administra su ciclo de vida y datos.
El venv existente debe incluir psycopg para verificar la conexión antes de parar
servicios. El Postgres local usa 5433. El deploy no administra contenedores.

WAHA se administra por separado en `/opt/codi/waha-prod` (proyecto
`codi-waha-prod`). Django usa `WAHA_BASE_URL=http://127.0.0.1:3004`,
`WAHA_API_KEY`, `WAHA_INSTANCIA=waha` y `WAHA_WEBHOOK_SECRET`. La configuración independiente de WAHA define `WHATSAPP_HOOK_URL` como URL
pública completa terminada en `/api/webhooks/waha/`, `WHATSAPP_HOOK_EVENTS=message`
y `WHATSAPP_HOOK_HMAC_KEY` igual a `WAHA_WEBHOOK_SECRET`. El callback debe ser
alcanzable desde el contenedor; loopback dentro de WAHA apunta al contenedor.
Django verifica la firma HMAC SHA-512 sobre el cuerpo original.
La API key y el HMAC son diferentes. `WEBHOOK_BASE_URL` sigue disponible para
pey y su callback `/api/webhooks/pey/` usa `PEY_WEBHOOK_SECRET` independiente.
El worker recibe solo configuración de base, modo y API WAHA; su `.env.canal`
tiene modo 600 y excluye secretos pey, HMAC y SMTP. El latido solo indica que
el worker funciona, no que WAHA esté conectado o tenga sesión vinculada.

El Postgres del job `backend:test` sigue con una contraseña efímera en el YAML, distinta de la del archivo. Las plantillas `.env.example` traen `PEY_ADAPTADOR=desarrollo`. Ese adaptador no usa `PEY_API_KEY`, `PEY_WEBHOOK_SECRET` ni `https://api.pey.mx`. `obtener_puerto()` lo rechaza cuando `PEY_API_KEY` tiene valor, para que un `DEBUG` encendido por error no conviva con la llave real.
