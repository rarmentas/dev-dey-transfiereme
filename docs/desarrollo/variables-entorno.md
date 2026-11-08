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
| `PEY_ADAPTADOR` | No | `backend/.env` | `desarrollo` o `produccion`. Vacío: `desarrollo` si `DEBUG`, si no `produccion`. `desarrollo` con `DEBUG=False` no arranca el puerto |

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
| `PEY_ADAPTADOR` | No | `desarrollo` o `produccion`. Vacío con `DEBUG=False`: adaptador de producción. `desarrollo` exige `DEBUG` |

Esas cuatro secretas no se repiten como variables sueltas. `scripts/ci-install-env.sh` copia el archivo a `backend/.env` con modo `600` y no imprime su contenido.

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

`DEPLOY_HOST` es el servidor, `DEPLOY_USER` quien entra por SSH, `DEPLOY_PORT` el puerto SSH y `DEPLOY_PATH` una ruta absoluta de al menos dos niveles, dedicada a la app (no el home). `PROD_SSH_PRIVATE_KEY` y `TEST_SSH_PRIVATE_KEY` son la llave privada en base64 de una sola línea (`base64 -w 0`). El job la decodifica a un archivo temporal y no la copia al `.env`. El script rechaza el archivo de la app si trae esas claves o un bloque `PRIVATE KEY`.

El pipeline solo se crea en un push (o un lanzamiento manual) a `master` o a `test`. `deploy:prod` usa el prefijo `PROD_` y el ámbito `production`; `deploy:test` usa `TEST_` y el ámbito `test`. Cada uno copia el árbol a su `DEPLOY_PATH`, instala el `.env` en `backend/.env`, levanta el Postgres de `deploy/compose.yaml` y espera a que responda, crea el venv, migra, publica estáticos, instala `cody.service` y espera HTTP 200 en `/api/salud/`. En intec-vps-001 ese contenedor es `codi-postgres` y publica `127.0.0.1:5435`; el archivo de la app tiene que traer `POSTGRES_PORT=5435`. Los datos quedan en `/var/lib/codi/postgres`, fuera del árbol que sincroniza el job. El usuario de deploy necesita `sudo` sin contraseña para `systemctl`, `install` y `mkdir`, y pertenecer al grupo `docker`. Opcional: `PROD_PYTHON` o `TEST_PYTHON` (por defecto `/opt/uv-python/cpython-3.12.14-linux-x86_64-gnu/bin/python3.12`, el mismo intérprete que denti). Dentro del archivo de la app se pueden fijar `GUNICORN_BIND` (por defecto `127.0.0.1:8000`), `GUNICORN_WORKERS` y `GUNICORN_TIMEOUT`. `DEBUG` tiene que ser `False`.

El Postgres del job `backend:test` sigue con una contraseña efímera en el YAML, distinta de la del archivo. Las plantillas `.env.example` traen `PEY_ADAPTADOR=desarrollo`. Ese adaptador no usa `PEY_API_KEY`, `PEY_WEBHOOK_SECRET` ni `https://api.pey.mx`.
