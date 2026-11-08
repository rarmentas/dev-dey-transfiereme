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
| `PEY_WEBHOOK_SECRET` | Sí | Firma Standard Webhooks (`whsec_...`) |

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

`DEPLOY_HOST` es el servidor, `DEPLOY_USER` quien entra por SSH, `DEPLOY_PORT` el puerto SSH y `DEPLOY_PATH` el directorio remoto. `PROD_SSH_PRIVATE_KEY` y `TEST_SSH_PRIVATE_KEY` son la llave privada en base64 de una sola línea (`base64 -w 0`). El job la decodifica a un archivo temporal y no la copia al `.env`. El script rechaza el archivo de la app si trae esas claves o un bloque `PRIVATE KEY`.

El Postgres del job `backend:test` sigue con una contraseña efímera en el YAML, distinta de la del archivo. El adaptador de desarrollo no consume `PEY_*`.
