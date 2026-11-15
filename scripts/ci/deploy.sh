#!/usr/bin/env bash
# Deploy normal de producción. El traslado inicial de /opt/codi se hace aparte.
set -euo pipefail

scope="${1:-}"
if [[ "$scope" != prod ]]; then
  echo 'deploy:test está bloqueado hasta tener infraestructura aislada.' >&2
  exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

# Rechazar el padre y cualquier destino arbitrario antes de copiar el .env.
remote_path="${PROD_DEPLOY_PATH:-}"
if [[ "$remote_path" != /opt/codi/prod ]]; then
  echo 'PROD_DEPLOY_PATH debe ser exactamente /opt/codi/prod.' >&2
  exit 2
fi

ssh_dir=""
guardian_pid=""
guardian_fd=""
SSH_PRIVATE_KEY_FILE=""
# shellcheck disable=SC2329 # Invocada por trap EXIT.
cleanup() {
  local result=$?
  trap - EXIT
  if [[ -n "$guardian_fd" ]]; then
    exec {guardian_fd}>&-
  fi
  if [[ -n "$guardian_pid" ]]; then
    wait "$guardian_pid" || result=1
  fi
  rm -f -- "${SSH_PRIVATE_KEY_FILE:-}"
  if [[ -n "$ssh_dir" ]]; then rm -rf -- "$ssh_dir"; fi
  exit "$result"
}
trap cleanup EXIT

# shellcheck disable=SC1091
source "$ROOT/scripts/ci-install-env.sh" prod
key_file="${SSH_PRIVATE_KEY_FILE:?}"
app_env="$ROOT/backend/.env"
ssh_port="${PROD_DEPLOY_PORT:?}"
ssh_host="${PROD_DEPLOY_HOST:?}"
ssh_user="${PROD_DEPLOY_USER:?}"
python_bin="${PROD_PYTHON:-/opt/uv-python/cpython-3.12.14-linux-x86_64-gnu/bin/python3.12}"

if [[ "$ssh_host" != 100.120.112.112 || "$ssh_port" != 30022 ]]; then
  echo 'Host o puerto de deploy no coinciden con el VPS inventariado.' >&2
  exit 2
fi
if [[ ! "$python_bin" =~ ^(/[A-Za-z0-9._-]+)+$ || "$python_bin" == *..* ]]; then
  echo 'PROD_PYTHON debe ser una ruta absoluta simple.' >&2
  exit 2
fi

if [[ ! "$ssh_user" =~ ^[a-z_][a-z0-9_-]*$ ]]; then
  echo 'PROD_DEPLOY_USER inválido.' >&2
  exit 2
fi
if [[ ! -f frontend/build/web/index.html || ! -f landing/dist/index.html ]]; then
  echo 'Faltan los artefactos web o de landing.' >&2
  exit 1
fi
if grep -Eqi '^[[:space:]]*DEBUG[[:space:]]*=[[:space:]]*(true|1|yes|on)[[:space:]]*$' "$app_env"; then
  echo 'DEBUG debe ser False en producción.' >&2
  exit 1
fi

health_line="$(grep -E '^[[:space:]]*ALLOWED_HOSTS[[:space:]]*=' "$app_env" | tail -1)"
health_host="${health_line#*=}"
health_host="${health_host%%#*}"
health_host="${health_host%%,*}"
health_host="${health_host//[[:space:]]/}"
if [[ ! "$health_host" =~ ^[A-Za-z0-9.-]+$ ]]; then
  echo 'ALLOWED_HOSTS no trae un host válido para comprobar la salud.' >&2
  exit 1
fi
health_port=8000
if bind_line="$(grep -E '^[[:space:]]*GUNICORN_BIND[[:space:]]*=' "$app_env" | tail -1)"; then
  bind_value="${bind_line#*=}"
  bind_value="${bind_value%%#*}"
  bind_value="${bind_value//[[:space:]]/}"
  health_port="${bind_value##*:}"
fi
if [[ ! "$health_port" =~ ^[0-9]+$ ]] || (( health_port < 1 || health_port > 65535 )); then
  echo 'GUNICORN_BIND no trae un puerto válido.' >&2
  exit 1
fi

ssh_dir="$(mktemp -d)"
chmod 700 "$ssh_dir"
known_hosts="${ssh_dir}/known_hosts"
install -m 600 "$ROOT/deploy/known_hosts.prod" "$known_hosts"
ssh_base=(-i "$key_file" -p "$ssh_port" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=15 -o StrictHostKeyChecking=yes -o "UserKnownHostsFile=$known_hosts")
remote="${ssh_user}@${ssh_host}"

# El proceso SSH conserva un flock remoto durante preflight, rsync y reinicio.
# /run/codi-maintenance bloquea nuevos deploys. Los jobs de commits viejos
# requieren además revocación temporal de su acceso SSH durante el corte.
mkfifo "$ssh_dir/hold"
ssh "${ssh_base[@]}" "$remote" \
  "bash -c 'set -e; exec 9>/run/lock/codi-deploy.lock; flock -n -x 9 || { echo LOCK_BUSY; exit 75; }; test ! -e /run/codi-maintenance || { echo MAINTENANCE; exit 76; }; echo READY; cat >/dev/null'" \
  <"$ssh_dir/hold" >"$ssh_dir/guardian.out" 2>&1 &
guardian_pid=$!
exec {guardian_fd}>"$ssh_dir/hold"
ready=0
for _ in $(seq 1 80); do
  if grep -qx READY "$ssh_dir/guardian.out"; then ready=1; break; fi
  if ! kill -0 "$guardian_pid" 2>/dev/null; then break; fi
  sleep 0.25
done
if (( ! ready )); then
  sed -n '1,5p' "$ssh_dir/guardian.out" >&2
  echo 'No se obtuvo el bloqueo remoto; no se sincronizó nada.' >&2
  exit 1
fi
guardian_alive() {
  if [[ "$(jobs -pr)" != "$guardian_pid" ]]; then
    echo 'Se perdió el bloqueo remoto; abortando el deploy.' >&2
    exit 1
  fi
}

ssh "${ssh_base[@]}" "$remote" bash -s -- "$remote_path" "$ssh_user" "$python_bin" \
  <"$ROOT/scripts/ci/preflight-remoto.sh"
guardian_alive

rsync_rsh="$(printf 'ssh -i %q -p %q -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=15 -o StrictHostKeyChecking=yes -o UserKnownHostsFile=%q' "$key_file" "$ssh_port" "$known_hosts")"
rsync -az --delete --safe-links --chmod=Du=rwx,Dgo=rx,Fu+rw,Fgo+r,Fgo-w -e "$rsync_rsh" \
  --exclude '/.git/' --exclude '/.agents/' --exclude '/.cursor/' \
  --exclude '/.tooling/' --exclude '/.temp-*' \
  --exclude '/backend/.env' --exclude '/backend/.env.incoming' \
  --exclude '/backend/.env.canal' --exclude '/backend/.env.cobros' \
  --exclude '/backend/.env.stt' \
  --exclude '/backend/.venv/' --exclude '/backend/staticfiles/' \
  --exclude '/frontend/.dart_tool/' --exclude '/frontend/.pub-cache/' \
  --exclude '/landing/node_modules/' --exclude '/landing/.astro/' \
  --exclude '/_bmad/' --exclude '/_bmad-output/' \
  --exclude '__pycache__/' --exclude '*.pyc' --exclude '.cache/' --exclude '.env' \
  backend frontend landing deploy scripts "${remote}:${remote_path}/"
guardian_alive

scp -i "$key_file" -P "$ssh_port" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=15 \
  -o StrictHostKeyChecking=yes -o "UserKnownHostsFile=$known_hosts" \
  "$app_env" "${remote}:${remote_path}/backend/.env.incoming"
guardian_alive

# Los argumentos se expanden localmente; todos tienen formatos restringidos arriba.
# shellcheck disable=SC2029
ssh "${ssh_base[@]}" "$remote" bash "$remote_path/scripts/ci/deploy-remoto.sh" \
  "$remote_path" "$python_bin" "$ssh_user" "$health_host" "$health_port"
guardian_alive
echo 'Deploy de producción terminado en /opt/codi/prod.'
