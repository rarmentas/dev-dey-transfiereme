#!/usr/bin/env bash
# Corre en el servidor, como PROD_DEPLOY_USER. Lo llama scripts/ci/deploy.sh.
# Instala el .env, el venv y la unit systemd, y espera /api/salud/.
set -euo pipefail

dest="${1:?Falta la ruta de deploy}"
python_bin="${2:?Falta el intérprete Python}"
service_user="${3:?Falta el usuario del servicio}"
health_host="${4:?Falta el host de la comprobación}"
health_port="${5:?Falta el puerto de la comprobación}"

if [[ ! "$dest" =~ ^(/[A-Za-z0-9._-]+){2,}$ || "$dest" == *..* ]]; then
  echo "Ruta de deploy rechazada." >&2
  exit 1
fi
if [[ "$dest" == "$HOME" || "$dest" == "/root" ]]; then
  echo "La ruta de deploy no puede ser el home del usuario." >&2
  exit 1
fi
if [[ -e "${dest}/.ssh" ]]; then
  echo "La ruta de deploy contiene .ssh. Use un directorio solo para la app." >&2
  exit 1
fi
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
  echo "No está el intérprete ${python_bin}. Defina PROD_PYTHON en GitLab." >&2
  exit 1
fi

if [[ "$(id -u)" -eq 0 ]]; then
  if systemctl is-active --quiet cody; then
    systemctl stop cody
  fi
elif sudo -n systemctl is-active --quiet cody; then
  as_root systemctl stop cody
fi

incoming="${dest}/backend/.env.incoming"
target="${dest}/backend/.env"
if [[ ! -f "$incoming" ]]; then
  echo "No llegó el archivo de entorno de la app." >&2
  exit 1
fi
sed -i 's/\r$//' "$incoming"
if [[ -e "$target" && ! -w "$target" ]]; then
  rm -f -- "$target"
fi
install -m 600 "$incoming" "$target"
rm -f "$incoming"

if [[ ! -x "${dest}/backend/.venv/bin/python" ]]; then
  echo "Creando el venv."
  "$python_bin" -m venv "${dest}/backend/.venv"
fi
"${dest}/backend/.venv/bin/pip" install -r "${dest}/backend/requirements.txt"

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

unit_tmp="$(mktemp)"
sed -e "s|@DEPLOY_PATH@|${dest}|g" -e "s|@DEPLOY_USER@|${service_user}|g" \
  "${dest}/deploy/cody.service.in" >"$unit_tmp"
as_root install -m 644 "$unit_tmp" /etc/systemd/system/cody.service
rm -f "$unit_tmp"
as_root systemctl daemon-reload
as_root systemctl enable cody
as_root systemctl restart cody
as_root systemctl is-active cody

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
    exit 0
  fi
  sleep 1
done

echo "Gunicorn no respondió 200 en 127.0.0.1:${health_port}/api/salud/ (último: ${codigo:-sin respuesta})." >&2
as_root journalctl -u cody -n 40 --no-pager >&2 || true
exit 1
