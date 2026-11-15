#!/usr/bin/env bash
# Corre en el servidor, como PROD_DEPLOY_USER. Lo llama scripts/ci/deploy.sh.
# Instala el .env, el venv y la unit systemd, y espera /api/salud/.
set -euo pipefail

scope="${1:-}"
dest="${2:-}"
python_bin="${3:?Falta el intérprete Python}"
service_user="${4:?Falta el usuario del servicio}"
health_host="${5:?Falta el host de la comprobación}"
health_port="${6:?Falta el puerto de la comprobación}"
unit_base="${7:-cody}"
token="${8:-}"

[[ "$scope" == prod && "$dest" == /opt/codi/prod && "$unit_base" == cody ]] || {
  echo "Scope, destino o unit rechazados." >&2; exit 1;
}
bash "$(dirname "$0")/deploy-guard.sh" check "$scope" "$dest"
lock=/opt/codi/.deploy.lock
[[ "$token" =~ ^[a-f0-9-]{36}$ && -f "$lock" && ! -L "$lock" &&
   ! -e /opt/codi/.maintenance && "$(cat "$lock")" == "$token" ]] || {
  echo "Falta la protección del deploy." >&2; exit 1;
}
if flock -n "$lock" true; then
  echo "El candado de deploy no está activo." >&2; exit 1
fi
[[ "$service_user" =~ ^[a-z_][a-z0-9_-]*$ ]] || exit 1
if [[ ! "$health_port" =~ ^[0-9]+$ ]]; then
  echo "Puerto de comprobación inválido." >&2
  exit 1
fi
if [[ ! "$health_host" =~ ^[A-Za-z0-9.-]+$ ]]; then
  echo "Host de comprobación inválido." >&2
  exit 1
fi

as_root() {
  if [[ "$(id -u)" -eq 0 ]]; then
    "$@"
    return
  fi
  sudo -n "$@"
}

if [[ "$(id -u)" -ne 0 ]] && ! sudo -n true; then
  echo "El usuario ${service_user} necesita sudo sin contraseña para systemctl e install." >&2
  exit 1
fi

if ! command -v "$python_bin" >/dev/null 2>&1 && [[ ! -x "$python_bin" ]]; then
  echo "No está el intérprete ${python_bin}. Defina PROD_PYTHON o TEST_PYTHON en GitLab." >&2
  exit 1
fi

incoming="${dest}/backend/.env.incoming"
target="${dest}/backend/.env"
[[ -f "$incoming" ]] || { echo "Falta el entorno entrante." >&2; exit 1; }
[[ -x "${dest}/backend/.venv/bin/python" ]] || {
  echo "Falta el venv operativo para verificar PostgreSQL; consulte a operación." >&2
  exit 1
}
identidad="$(docker inspect --format '{{.State.Running}} {{index .Config.Labels "com.docker.compose.project"}} {{index .Config.Labels "com.docker.compose.service"}}' codi-postgres 2>/dev/null || true)"
puerto="$(docker inspect --format '{{range (index .NetworkSettings.Ports "5432/tcp")}}{{.HostIp}}:{{.HostPort}}{{end}}' codi-postgres 2>/dev/null || true)"
[[ "$identidad" == "true codi postgres" && "$puerto" == "127.0.0.1:5435" ]] || {
  echo "PostgreSQL ausente o detenido; consulte a operación." >&2; exit 1;
}
if ! "${dest}/backend/.venv/bin/python" - "$incoming" <<'PYDB'
import sys
from pathlib import Path
import psycopg

valores = {}
for linea in Path(sys.argv[1]).read_text().splitlines():
    if "=" in linea and not linea.lstrip().startswith("#"):
        clave, valor = linea.split("=", 1)
        valores[clave.strip()] = valor.strip()
try:
    if valores.get("POSTGRES_HOST") != "127.0.0.1" or valores.get("POSTGRES_PORT") != "5435":
        raise ValueError("destino PostgreSQL inesperado")
    with psycopg.connect(host=valores["POSTGRES_HOST"], port=valores["POSTGRES_PORT"],
                         dbname=valores["POSTGRES_DB"], user=valores["POSTGRES_USER"],
                         password=valores["POSTGRES_PASSWORD"], connect_timeout=5) as conexion:
        conexion.execute("SELECT 1")
except Exception:
    sys.exit(1)
PYDB
then
  echo "PostgreSQL no accesible con el entorno entrante; consulte a operación." >&2
  exit 1
fi

unit_dir="$(mktemp -d)"
trap 'rm -rf "$unit_dir"' EXIT
for suffix in "" "-canal"; do
  archivo="$unit_dir/cody${suffix}.service"
  sed -e "s|@DEPLOY_PATH@|${dest}|g" -e "s|@DEPLOY_USER@|${service_user}|g" \
    -e "s|@UNIT_BASE@|${unit_base}|g" \
    "${dest}/deploy/cody${suffix}.service.in" >"$archivo"
  ! grep -Eq '@[A-Z_]+@' "$archivo" || exit 1
  ! sed "s|$dest/|/|g; s|$dest$||g" "$archivo" | grep -q '/opt/codi' || exit 1
  grep -Fxq "WorkingDirectory=$dest/backend" "$archivo" || exit 1
  grep -Fxq "ReadWritePaths=$dest" "$archivo" || exit 1
done
grep -Fxq "EnvironmentFile=$dest/backend/.env" "$unit_dir/cody.service"
grep -Fq "ExecStart=$dest/backend/.venv/bin/gunicorn " "$unit_dir/cody.service"
grep -Fxq "RuntimeDirectory=cody" "$unit_dir/cody.service"
grep -Fq -- "--pid /run/cody/gunicorn.pid" "$unit_dir/cody.service"
grep -Fxq "EnvironmentFile=$dest/backend/.env.canal" "$unit_dir/cody-canal.service"
grep -Fxq "ExecStart=$dest/backend/.venv/bin/python manage.py procesar_canal" "$unit_dir/cody-canal.service"
for unit in "${unit_base}-canal" "$unit_base"; do
  if as_root systemctl is-active --quiet "$unit"; then
    as_root systemctl stop "$unit"
  fi
done
install -m 600 "$incoming" "$target"
rm -f "$incoming"

"${dest}/backend/.venv/bin/pip" install -r "${dest}/backend/requirements-canal.txt"

eval "$("${dest}/backend/.venv/bin/python" -c '
import shlex
import sys
from pathlib import Path

for raw in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    line = raw.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    key = key.strip()
    if not key.replace("_", "").isalnum():
        continue
    print(f"export {key}={shlex.quote(value.strip())}")
' "$target")"
(
  cd "${dest}/backend"
  ./.venv/bin/python manage.py migrate --noinput
  ./.venv/bin/python manage.py collectstatic --noinput
)

canal_env="${dest}/backend/.env.canal"
umask 077
# Solo las variables necesarias para Django y el worker, sin secretos web.
grep -E '^[[:space:]]*(POSTGRES_DB|POSTGRES_USER|POSTGRES_PASSWORD|POSTGRES_HOST|POSTGRES_PORT|DJANGO_SECRET_KEY|DEBUG|ALLOWED_HOSTS|DEMO_MODE|DEMO_PEY_BANK_ACCOUNT_ID|NUCLEO_ADAPTADOR|POLITICA_COBRO_VERSION|PEDIDOS_COBRO_HABILITADO|WAHA_INSTANCIA|WAHA_BASE_URL|WAHA_API_KEY)[[:space:]]*=' \
  "$target" >"$canal_env" || [[ "$?" -eq 1 ]]
chmod 600 "$canal_env"

for suffix in "" "-canal"; do
  as_root install -m 644 "$unit_dir/cody${suffix}.service" \
    "/etc/systemd/system/${unit_base}${suffix}.service"
done
as_root systemctl daemon-reload
as_root systemctl enable "$unit_base" "${unit_base}-canal"
as_root systemctl restart "$unit_base"
as_root systemctl is-active "$unit_base"

codigo=""
for _ in $(seq 1 30); do
  codigo="$("${dest}/backend/.venv/bin/python" -c "
import urllib.request
req = urllib.request.Request(
    'http://127.0.0.1:${health_port}/api/salud/',
    headers={'Host': '${health_host}'},
)
try:
    with urllib.request.urlopen(req, timeout=2) as resp:
        print(resp.status)
except Exception:
    print('')
")"
  if [[ "$codigo" == "200" ]]; then
    echo "salud 200"
    break
  fi
  sleep 1
done

if [[ "$codigo" != "200" ]]; then
  echo "Gunicorn no respondió 200 en 127.0.0.1:${health_port}/api/salud/ (último: ${codigo:-sin respuesta})." >&2
  as_root journalctl -u "$unit_base" -n 40 --no-pager >&2 || true
  exit 1
fi

inicio_canal="$("${dest}/backend/.venv/bin/python" -c \
  'from datetime import datetime, timezone; print(datetime.now(timezone.utc).isoformat())')"
as_root systemctl restart "${unit_base}-canal"
for _ in $(seq 1 30); do
  if (cd "${dest}/backend" && ./.venv/bin/python manage.py estado_canal \
    --max-edad 30 --desde "$inicio_canal") && \
    as_root systemctl is-active --quiet "${unit_base}-canal"; then
    exit 0
  fi
  sleep 1
done
echo "El canal no registró un latido reciente." >&2
as_root journalctl -u "${unit_base}-canal" -n 40 --no-pager >&2 || true
exit 1
