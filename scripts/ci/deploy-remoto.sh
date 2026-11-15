#!/usr/bin/env bash
# Completa un deploy normal después del preflight y rsync de deploy.sh.
set -euo pipefail
umask 077

dest="${1:-}"
python_bin="${2:-}"
service_user="${3:-}"
health_host="${4:-}"
health_port="${5:-}"
if [[ "$dest" != /opt/codi/prod || ! "$service_user" =~ ^[a-z_][a-z0-9_-]*$ ||
      ! "$health_host" =~ ^[A-Za-z0-9.-]+$ || ! "$health_port" =~ ^[0-9]+$ ]]; then
  echo 'Argumentos de deploy remoto inválidos.' >&2
  exit 2
fi
if [[ -e /run/codi-maintenance ]]; then
  echo 'CoDi está en mantenimiento.' >&2
  exit 1
fi
if [[ ! -e /run/lock/codi-deploy.lock ]] || flock -n -x /run/lock/codi-deploy.lock true; then
  echo 'Falta el bloqueo remoto del deploy.' >&2
  exit 1
fi
for path in /opt/codi "$dest" "$dest/backend" "$dest/deploy" \
  "$dest/backend/.venv" "$dest/backend/staticfiles" "$dest/backend/.env.canal"; do
  if [[ -L "$path" ]]; then echo "Enlace no permitido: $path" >&2; exit 1; fi
done
if [[ "$(realpath -e -- "$dest")" != "$dest" || ! -w "$dest" ||
      "$(systemctl show cody.service -p WorkingDirectory --value)" != "$dest/backend" ]]; then
  echo 'El destino o la unit activa no coinciden con /opt/codi/prod.' >&2
  exit 1
fi
if [[ ! -x "$python_bin" ]] ||
   [[ "$(docker inspect codi-postgres --format '{{.State.Health.Status}}' 2>/dev/null)" != healthy ]]; then
  echo 'Falta Python o PostgreSQL no está sano.' >&2
  exit 1
fi

incoming="$dest/backend/.env.incoming"
target="$dest/backend/.env"
if [[ ! -f "$incoming" || -L "$incoming" || ! -f "$target" || -L "$target" ]]; then
  echo 'Falta el entorno entrante o el entorno actual no es regular.' >&2
  exit 1
fi

env_val() {
  local key="$1" line
  line="$(grep -E "^[[:space:]]*${key}[[:space:]]*=" "$incoming" | tail -1 || true)"
  line="${line#*=}"
  line="${line%%#*}"
  line="${line#"${line%%[![:space:]]*}"}"
  line="${line%"${line##*[![:space:]]}"}"
  printf '%s' "$line"
}
if [[ "$(env_val POSTGRES_PORT)" != 5435 ]]; then
  echo 'POSTGRES_PORT debe ser 5435.' >&2
  exit 1
fi

backup_dir="$(mktemp -d)"
unit_tmp="$backup_dir/cody.service"
committed=0
stopped=0
# shellcheck disable=SC2329 # Invocada por trap EXIT.
cleanup() {
  local result=$?
  trap - EXIT
  if (( result != 0 && stopped && ! committed )); then
    echo 'El arranque falló; restaurando units y entornos previos.' >&2
    sudo -n systemctl stop cody-canal.service || true
    if [[ ! -f "$backup_dir/canal.enabled" ]]; then
      sudo -n systemctl disable cody-canal.service || true
    fi
    if [[ -f "$backup_dir/cody-canal.service.previous" ]]; then
      sudo -n install -m 644 "$backup_dir/cody-canal.service.previous" /etc/systemd/system/cody-canal.service || true
    else
      sudo -n rm -f -- /etc/systemd/system/cody-canal.service || true
    fi
    if [[ -f "$backup_dir/.env.canal" ]]; then
      install -m 600 "$backup_dir/.env.canal" "$dest/backend/.env.canal" || true
    else
      rm -f -- "$dest/backend/.env.canal"
    fi
    sudo -n install -m 644 "$backup_dir/cody.service.previous" /etc/systemd/system/cody.service || true
    install -m 600 "$backup_dir/.env" "$target" || true
    sudo -n systemctl daemon-reload || true
    sudo -n systemctl start cody.service || true
    sudo -n systemctl is-active cody.service || true
    if [[ -f "$backup_dir/canal.enabled" ]]; then
      sudo -n systemctl enable cody-canal.service || true
    fi
    if [[ -f "$backup_dir/canal.active" ]]; then
      sudo -n systemctl start cody-canal.service || true
    fi
  fi
  rm -f -- "$incoming" "$unit_tmp"
  rm -rf -- "$backup_dir"
  exit "$result"
}
trap cleanup EXIT

# Cargar solo claves de entorno válidas, con valores escapados por shlex.
# No se imprime el archivo ni las exportaciones.
eval "$("$python_bin" -c '
import shlex
import sys
from pathlib import Path

for raw in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    line = raw.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    key = key.strip()
    if not key or not (key[0].isalpha() or key[0] == "_"):
        continue
    if not all(c.isalnum() or c == "_" for c in key):
        continue
    print(f"export {key}={shlex.quote(value.strip())}")
' "$incoming")"

if [[ ! -x "$dest/backend/.venv/bin/python" ]]; then
  "$python_bin" -m venv "$dest/backend/.venv"
fi
"$dest/backend/.venv/bin/pip" install --disable-pip-version-check --no-input -r "$dest/backend/requirements-canal.txt"
(
  cd "$dest/backend"
  ./.venv/bin/python manage.py check
  ./.venv/bin/python manage.py migrate --check --noinput
  ./.venv/bin/python manage.py collectstatic --noinput
)
chmod -R u+rwX,go-rwx "$dest/backend/.venv"
chmod -R u+rwX,go+rX,go-w "$dest/backend/staticfiles"

# Preparar ambas units y el entorno del canal antes de detener servicios.
for suffix in "" "-canal"; do
  unit_tmp="$backup_dir/cody${suffix}.service"
  sed -e "s|@DEPLOY_PATH@|$dest|g" -e "s|@DEPLOY_USER@|$service_user|g" \
    -e 's|@UNIT_BASE@|cody|g' \
    "$dest/deploy/cody${suffix}.service.in" >"$unit_tmp"
  if grep -Eq '@[A-Z_]+@' "$unit_tmp"; then
    echo 'La unit conserva marcadores sin sustituir.' >&2
    exit 1
  fi
  systemd-analyze verify "$unit_tmp" >/dev/null
done
canal_env="$backup_dir/env.canal"
# Solo las variables necesarias para Django y el worker, sin secretos web.
grep -E '^[[:space:]]*(POSTGRES_DB|POSTGRES_USER|POSTGRES_PASSWORD|POSTGRES_HOST|POSTGRES_PORT|DJANGO_SECRET_KEY|DEBUG|ALLOWED_HOSTS|DEMO_MODE|DEMO_PEY_BANK_ACCOUNT_ID|NUCLEO_ADAPTADOR|POLITICA_COBRO_VERSION|PEDIDOS_COBRO_HABILITADO|WAHA_INSTANCIA|WAHA_BASE_URL|WAHA_API_KEY)[[:space:]]*=' \
  "$incoming" >"$canal_env" || [[ "$?" -eq 1 ]]
chmod 600 "$canal_env"

cp -p /etc/systemd/system/cody.service "$backup_dir/cody.service.previous"
cp -p "$target" "$backup_dir/.env"
if [[ -f /etc/systemd/system/cody-canal.service ]]; then
  cp -p /etc/systemd/system/cody-canal.service "$backup_dir/cody-canal.service.previous"
fi
if [[ -f "$dest/backend/.env.canal" ]]; then
  cp -p "$dest/backend/.env.canal" "$backup_dir/.env.canal"
fi
if systemctl is-active --quiet cody-canal.service; then
  touch "$backup_dir/canal.active"
fi
if systemctl is-enabled --quiet cody-canal.service; then
  touch "$backup_dir/canal.enabled"
fi
sudo -n true
stopped=1
if [[ -f "$backup_dir/canal.active" ]]; then
  sudo -n systemctl stop cody-canal.service
fi
sudo -n systemctl stop cody.service
install -m 600 "$incoming" "$target"
install -m 600 "$canal_env" "$dest/backend/.env.canal"
for suffix in "" "-canal"; do
  sudo -n install -m 644 "$backup_dir/cody${suffix}.service" "/etc/systemd/system/cody${suffix}.service"
done
sudo -n systemctl daemon-reload
sudo -n systemctl start cody.service

for _ in $(seq 1 30); do
  code="$(curl -sS --max-time 2 -o /dev/null -w '%{http_code}' \
    -H "Host: $health_host" "http://127.0.0.1:$health_port/api/salud/" 2>/dev/null || true)"
  if [[ "$code" == 200 ]]; then
    break
  fi
  sleep 1
done
if [[ "$code" != 200 ]]; then
  echo 'CoDi no respondió 200 tras el arranque.' >&2
  exit 1
fi

inicio_canal="$("$dest/backend/.venv/bin/python" -c \
  'from datetime import datetime, timezone; print(datetime.now(timezone.utc).isoformat())')"
sudo -n systemctl restart cody-canal.service
for _ in $(seq 1 30); do
  if (cd "$dest/backend" && ./.venv/bin/python manage.py estado_canal \
      --max-edad 30 --desde "$inicio_canal") && \
     systemctl is-active --quiet cody-canal.service; then
    sudo -n systemctl enable cody-canal.service
    committed=1
    echo 'CoDi y canal sanos en /opt/codi/prod; PostgreSQL no se recreó.'
    exit 0
  fi
  sleep 1
done
echo 'El canal no registró un latido reciente o su unit no está activa.' >&2
exit 1
