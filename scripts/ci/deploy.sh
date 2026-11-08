#!/usr/bin/env bash
# Deploy de producción desde GitLab CI. Lo invoca el job deploy:prod.
# Requiere bash. La imagen alpine trae /bin/sh y no soporta arrays ni [[ ]].
set -euo pipefail

scope="${1:-}"
if [[ "$scope" != "prod" ]]; then
  echo "Indique prod." >&2
  exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

trap 'rm -f "${SSH_PRIVATE_KEY_FILE:-}"' EXIT
# shellcheck disable=SC1091
source "$ROOT/scripts/ci-install-env.sh" prod

key_file="${SSH_PRIVATE_KEY_FILE:?}"
app_env="$ROOT/backend/.env"
remote_path="${PROD_DEPLOY_PATH%/}"
ssh_port="$PROD_DEPLOY_PORT"
ssh_host="$PROD_DEPLOY_HOST"
ssh_user="$PROD_DEPLOY_USER"
python_bin="${PROD_PYTHON:-python3.12}"

if grep -Eq '^[[:space:]]*DEBUG[[:space:]]*=[[:space:]]*(True|true|1|yes|on)[[:space:]]*$' "$app_env"; then
  echo "DEBUG debe ser False en producción." >&2
  exit 1
fi

if [[ ! "$remote_path" =~ ^(/[A-Za-z0-9._-]+){2,}$ || "$remote_path" == *..* ]]; then
  echo "PROD_DEPLOY_PATH debe ser una ruta absoluta de al menos dos niveles, sin '..'." >&2
  exit 1
fi

if [[ ! "$ssh_user" =~ ^[a-z_][a-z0-9_-]*$ ]]; then
  echo "PROD_DEPLOY_USER no es un nombre de usuario válido." >&2
  exit 1
fi

if [[ ! -d frontend/build/web ]]; then
  echo "Falta frontend/build/web. El job de build no entregó el artefacto." >&2
  exit 1
fi

health_line="$(grep -E '^[[:space:]]*ALLOWED_HOSTS[[:space:]]*=' "$app_env" | tail -1)"
health_host="${health_line#*=}"
health_host="${health_host%%#*}"
health_host="${health_host%%,*}"
health_host="${health_host//[[:space:]]/}"
if [[ ! "$health_host" =~ ^[A-Za-z0-9.-]+$ ]]; then
  echo "ALLOWED_HOSTS no trae un host utilizable para comprobar /api/salud/." >&2
  exit 1
fi

health_port="8000"
if bind_line="$(grep -E '^[[:space:]]*GUNICORN_BIND[[:space:]]*=' "$app_env" | tail -1)"; then
  bind_value="${bind_line#*=}"
  bind_value="${bind_value%%#*}"
  bind_value="${bind_value//[[:space:]]/}"
  health_port="${bind_value##*:}"
fi
if [[ ! "$health_port" =~ ^[0-9]+$ ]]; then
  echo "GUNICORN_BIND no trae un puerto numérico." >&2
  exit 1
fi

mkdir -p "${HOME}/.ssh"
chmod 700 "${HOME}/.ssh"
: >"${HOME}/.ssh/known_hosts"
if ! ssh-keyscan -p "$ssh_port" -T 15 -H "$ssh_host" >>"${HOME}/.ssh/known_hosts"; then
  echo "ssh-keyscan falló contra ${ssh_host}:${ssh_port}." >&2
  exit 1
fi
if [[ ! -s "${HOME}/.ssh/known_hosts" ]]; then
  echo "El runner no llega a ${ssh_host}:${ssh_port}." >&2
  exit 1
fi

ssh_base=(-i "$key_file" -p "$ssh_port" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=15)
remote="${ssh_user}@${ssh_host}"

echo "Desplegando en ${remote}:${ssh_port} ${remote_path}"
ssh "${ssh_base[@]}" "$remote" mkdir -p "${remote_path}/backend" "${remote_path}/frontend"

remote_home="$(ssh "${ssh_base[@]}" "$remote" 'printf %s "$HOME"')"
if [[ "$remote_path" == "$remote_home" ]]; then
  echo "PROD_DEPLOY_PATH no puede ser el home del usuario." >&2
  exit 1
fi
if ssh "${ssh_base[@]}" "$remote" test -e "${remote_path}/.ssh"; then
  echo "PROD_DEPLOY_PATH contiene .ssh. Use un directorio solo para la app." >&2
  exit 1
fi

rsync_rsh="$(printf 'ssh -i %q -p %q -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=15' "$key_file" "$ssh_port")"
rsync -az --delete -e "$rsync_rsh" \
  --exclude '.git/' \
  --exclude '.tooling/' \
  --exclude 'backend/.venv/' \
  --exclude 'backend/staticfiles/' \
  --exclude 'backend/.env' \
  --exclude 'backend/.env.incoming' \
  --exclude 'frontend/.dart_tool/' \
  --exclude 'frontend/.pub-cache/' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude '.env' \
  --exclude '.cache/' \
  --exclude '_bmad/' \
  --exclude '_bmad-output/' \
  --exclude '.agents/' \
  --exclude '.cursor/' \
  ./ "${remote}:${remote_path}/"

scp -i "$key_file" -P "$ssh_port" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=15 \
  "$app_env" \
  "${remote}:${remote_path}/backend/.env.incoming"

ssh "${ssh_base[@]}" "$remote" \
  bash "${remote_path}/scripts/ci/deploy-remoto.sh" \
  "$remote_path" "$python_bin" "$ssh_user" "$health_host" "$health_port"

echo "Listo. Cody responde en el servidor."
