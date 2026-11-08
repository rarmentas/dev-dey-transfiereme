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

Plantilla: `backend/.env.example`. `scripts/dev-start.sh` carga `backend/.env` si existe y **no** exige variables de pey.

## Producción e integración con pey (documentadas; no usadas en dev-start del scaffold)

| Variable | Secreta | Dónde vive | Para qué |
| --- | --- | --- | --- |
| `PEY_API_KEY` | **Sí** | `backend/.env` en servidor; variable tipo File en GitLab al desplegar | Bearer contra `https://api.pey.mx` |
| `PEY_WEBHOOK_SECRET` | **Sí** | Igual que arriba | Verificación Standard Webhooks (`whsec_...`) |
| `WEBHOOK_BASE_URL` | No (URL pública) | Servidor | Base pública de avisos; constraint C10: `https://transfiereme.asware.com.mx` |
| `POSTGRES_*` | Password sí | Servidor | Postgres de producción |
| `DJANGO_SECRET_KEY` | Sí | Servidor | Django en producción |
| `DEBUG` | No | Servidor | Debe ser `False` |
| `ALLOWED_HOSTS` | No | Servidor | Dominios del despliegue |

El **adaptador de desarrollo** (stack) no consume `PEY_*`; los MR de cobro real las activan en el camino de integración.
