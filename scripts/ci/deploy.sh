#!/usr/bin/env bash
# Deploy desde GitLab CI (test/prod). Lo invocan deploy:test y deploy:prod.
# Requiere bash. La imagen alpine trae /bin/sh y no soporta arrays ni [[ ]].
set -euo pipefail

scope="${1:-}"
case "$scope" in
  prod) prefix="PROD" ;;
  test) echo "Deploy test deshabilitado." >&2; exit 2 ;;
  *)
    echo "Indique prod o test." >&2
    exit 2
    ;;
esac

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

ssh_dir=""
trap 'rm -f "${SSH_PRIVATE_KEY_FILE:-}"; rm -rf "${ssh_dir:-}"' EXIT
# shellcheck disable=SC1091
source "$ROOT/scripts/ci-install-env.sh" "$scope"

ci_val() {
  local name="${prefix}_$1"
  printf '%s' "${!name}"
}

key_file="${SSH_PRIVATE_KEY_FILE:?}"
app_env="$ROOT/backend/.env"
remote_path="$(ci_val DEPLOY_PATH)"

ssh_port="$(ci_val DEPLOY_PORT)"
ssh_host="$(ci_val DEPLOY_HOST)"
ssh_user="$(ci_val DEPLOY_USER)"
unit_base_var="${prefix}_UNIT_BASE"
unit_base="${!unit_base_var:-cody}"
if [[ "$unit_base" != cody ]]; then
  echo "${unit_base_var} no es un nombre de unit válido." >&2
  exit 1
fi
python_var="${prefix}_PYTHON"
python_bin="${!python_var:-/opt/uv-python/cpython-3.12.14-linux-x86_64-gnu/bin/python3.12}"

if grep -Eq '^[[:space:]]*DEBUG[[:space:]]*=[[:space:]]*(True|true|1|yes|on)[[:space:]]*$' "$app_env"; then
  echo "DEBUG debe ser False en ${scope}." >&2
  exit 1
fi

if [[ "$remote_path" != /opt/codi/prod ]]; then
  echo "Destino de producción rechazado." >&2
  exit 1
fi

if [[ ! "$ssh_user" =~ ^[a-z_][a-z0-9_-]*$ ]]; then
  echo "${prefix}_DEPLOY_USER no es un nombre de usuario válido." >&2
  exit 1
fi

if [[ ! -d frontend/build/web ]]; then
  echo "Falta frontend/build/web. El job de build no entregó el artefacto." >&2
  exit 1
fi

if [[ ! -f landing/dist/index.html ]]; then
  echo "Falta landing/dist. El job build:landing no entregó el artefacto." >&2
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

ssh_dir="$(mktemp -d)"
chmod 700 "$ssh_dir"
known_hosts="${ssh_dir}/known_hosts"
if ! ssh-keyscan -p "$ssh_port" -T 15 -H "$ssh_host" >>"$known_hosts"; then
  echo "ssh-keyscan falló contra ${ssh_host}:${ssh_port}." >&2
  exit 1
fi
if [[ ! -s "$known_hosts" ]]; then
  echo "El runner no llega a ${ssh_host}:${ssh_port}." >&2
  exit 1
fi

ssh_base=(-i "$key_file" -p "$ssh_port" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=15 -o "UserKnownHostsFile=${known_hosts}")
remote="${ssh_user}@${ssh_host}"

echo "Desplegando en ${remote}:${ssh_port} ${remote_path}"
# El guard cubre los intervalos con flock compartido; el receptor de rsync, el
# escritor del env y deploy-remoto.sh sostienen su propio flock compartido.
guard_script="$(cat scripts/ci/deploy-guard.sh)"
guard_command="$(printf 'bash -c %q -- lock %q %q' "$guard_script" "$scope" "$remote_path")"
coproc GUARD { ssh "${ssh_base[@]}" "$remote" "$guard_command"; }
guard_pid=$GUARD_PID
guard_out=${GUARD[0]}
guard_in=${GUARD[1]}
trap 'exec {guard_in}>&-; wait "$guard_pid" || true; rm -f "${SSH_PRIVATE_KEY_FILE:-}"; rm -rf "${ssh_dir:-}"' EXIT
if ! read -r -t 30 respuesta token <&"$guard_out" || \
  [[ "$respuesta" != READY || ! "$token" =~ ^[a-f0-9-]{36}$ ]]; then
  echo "No se obtuvo el candado remoto." >&2
  exit 1
fi
# La sesión del candado debe seguir viva durante toda la operación.
kill -0 "$guard_pid"
rsync_rsh="$(printf 'ssh -i %q -p %q -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=15 -o UserKnownHostsFile=%q' "$key_file" "$ssh_port" "$known_hosts")"
guard_con() {
  printf 'bash -c %q -- %q %q %q %q' "$guard_script" "$1" "$scope" "$remote_path" "$token"
}
rsync -az --delete -e "$rsync_rsh" --rsync-path "$(guard_con rsync)" \
  --exclude '.git/' \
  --exclude '.plan/' \
  --exclude '.tooling/' \
  --exclude 'backend/.venv/' \
  --exclude 'backend/staticfiles/' \
  --exclude 'backend/.env' \
  --exclude 'backend/.env.incoming' \
  --exclude 'backend/.env.canal' \
  --exclude 'frontend/.dart_tool/' \
  --exclude 'landing/node_modules/' \
  --exclude 'landing/.astro/' \
  --exclude 'frontend/.pub-cache/' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude '.env' \
  --exclude '.cache/' \
  --exclude '_bmad/' \
  --exclude '_bmad-output/' \
  --exclude '.agents/' \
  --exclude '.cursor/' \
  --exclude '*.tmp' \
  --exclude '*.lock' \
  --include '/backend/***' \
  --include '/frontend/***' \
  --include '/landing/***' \
  --include '/deploy/***' \
  --include '/scripts/***' \
  --exclude '*' \
  ./ "${remote}:${remote_path}/"

kill -0 "$guard_pid"
ssh "${ssh_base[@]}" "$remote" "$(guard_con env)" <"$app_env"

kill -0 "$guard_pid"
ssh "${ssh_base[@]}" "$remote" \
  bash "${remote_path}/scripts/ci/deploy-remoto.sh" \
  "$scope" "$remote_path" "$python_bin" "$ssh_user" "$health_host" "$health_port" "$unit_base" "$token"

echo "Listo. Cody responde en el servidor."
