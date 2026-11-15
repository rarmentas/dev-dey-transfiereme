#!/usr/bin/env bash
# Ensayo local del orquestador con SSH/rsync falsos; no toca el VPS.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
scratch="$(mktemp -d)"
trap 'rm -rf "$scratch"' EXIT
mkdir -p "$scratch/repo/scripts/ci" "$scratch/repo/backend" "$scratch/repo/deploy" \
  "$scratch/repo/frontend/build/web" "$scratch/repo/landing/dist" "$scratch/bin"
cp "$root/scripts/ci/deploy.sh" "$scratch/repo/scripts/ci/"
cp "$root/scripts/ci/preflight-remoto.sh" "$scratch/repo/scripts/ci/"
cp "$root/scripts/ci-install-env.sh" "$scratch/repo/scripts/"
cp "$root/deploy/known_hosts.prod" "$scratch/repo/deploy/"
printf 'web\n' >"$scratch/repo/frontend/build/web/index.html"
printf 'landing\n' >"$scratch/repo/landing/dist/index.html"
cat >"$scratch/ci.env" <<'ENV'
POSTGRES_DB=cody
POSTGRES_USER=cody
POSTGRES_PASSWORD=example
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5435
DJANGO_SECRET_KEY=example
DEBUG=False
ALLOWED_HOSTS=transfiereme.example
WEBHOOK_BASE_URL=https://transfiereme.example
PEY_API_KEY=example
PEY_WEBHOOK_SECRET=example
ENV

cat >"$scratch/bin/ssh" <<'MOCK'
#!/usr/bin/env bash
printf 'ssh\n' >>"$CALLS"
if [[ " $* " == *'codi-deploy.lock'* ]]; then
  if [[ "${LOCK_BUSY:-}" == 1 ]]; then echo LOCK_BUSY; exit 75; fi
  echo READY
  cat >/dev/null
elif [[ " $* " == *'bash -s --'* ]]; then
  cat >/dev/null
  [[ "${FAIL_PREFLIGHT:-}" != 1 ]]
fi
MOCK
cat >"$scratch/bin/rsync" <<'MOCK'
#!/usr/bin/env bash
printf 'rsync\n' >>"$CALLS"
args=("$@")
n=${#args[@]}
[[ "${args[n-6]} ${args[n-5]} ${args[n-4]} ${args[n-3]} ${args[n-2]}" == 'backend frontend landing deploy scripts' ]] || {
  printf 'Fuentes inesperadas: %s\n' "${args[*]: -6}" >&2
  exit 1
}
[[ "${FAIL_RSYNC:-}" != 1 ]]
MOCK
cat >"$scratch/bin/scp" <<'MOCK'
#!/usr/bin/env bash
printf 'scp\n' >>"$CALLS"
MOCK
chmod 755 "$scratch/bin/"*

export PATH="$scratch/bin:$PATH"
export CALLS="$scratch/calls"
export PROD_ENV_FILE="$scratch/ci.env"
export PROD_DEPLOY_HOST=100.120.112.112 PROD_DEPLOY_USER=rarme PROD_DEPLOY_PORT=30022
export PROD_SSH_PRIVATE_KEY_V2
PROD_SSH_PRIVATE_KEY_V2="$(printf '%s\n' '-----BEGIN PRIVATE KEY-----' 'fake' '-----END PRIVATE KEY-----' | base64 -w 0)"

expect_failure_without_transfer() {
  local label="$1"
  shift
  : >"$CALLS"
  if "$@" >"$scratch/output" 2>&1; then
    echo "Se esperaba rechazo: $label" >&2
    exit 1
  fi
  if grep -Eq '^(rsync|scp)$' "$CALLS"; then
    echo "Se transfirieron archivos en caso rechazado: $label" >&2
    exit 1
  fi
}

PROD_DEPLOY_PATH=/opt/codi
export PROD_DEPLOY_PATH
expect_failure_without_transfer padre bash "$scratch/repo/scripts/ci/deploy.sh" prod
PROD_DEPLOY_PATH=/opt/codi/test
expect_failure_without_transfer scope_cruzado bash "$scratch/repo/scripts/ci/deploy.sh" prod
PROD_DEPLOY_PATH=/opt/codi/prod
expect_failure_without_transfer test bash "$scratch/repo/scripts/ci/deploy.sh" test
export PROD_SSH_PRIVATE_KEY="$PROD_SSH_PRIVATE_KEY_V2"
unset PROD_SSH_PRIVATE_KEY_V2
expect_failure_without_transfer clave_antigua bash "$scratch/repo/scripts/ci/deploy.sh" prod
grep -q 'PROD_SSH_PRIVATE_KEY_V2' "$scratch/output"
export PROD_SSH_PRIVATE_KEY_V2="$PROD_SSH_PRIVATE_KEY"
unset PROD_SSH_PRIVATE_KEY
PROD_PYTHON='/tmp/python;exit 0'
export PROD_PYTHON
expect_failure_without_transfer python_inseguro bash "$scratch/repo/scripts/ci/deploy.sh" prod
unset PROD_PYTHON
LOCK_BUSY=1
export LOCK_BUSY
expect_failure_without_transfer bloqueo bash "$scratch/repo/scripts/ci/deploy.sh" prod
unset LOCK_BUSY
FAIL_PREFLIGHT=1
export FAIL_PREFLIGHT
expect_failure_without_transfer preflight bash "$scratch/repo/scripts/ci/deploy.sh" prod
unset FAIL_PREFLIGHT
FAIL_RSYNC=1
export FAIL_RSYNC
: >"$CALLS"
if bash "$scratch/repo/scripts/ci/deploy.sh" prod >"$scratch/output" 2>&1; then
  echo 'Se esperaba fallo de rsync.' >&2
  exit 1
fi
if grep -qx scp "$CALLS"; then
  echo 'Se copió el .env después de fallar rsync.' >&2
  exit 1
fi
unset FAIL_RSYNC
: >"$CALLS"
if ! bash "$scratch/repo/scripts/ci/deploy.sh" prod >"$scratch/output" 2>&1; then
  cat "$scratch/output" >&2
  exit 1
fi
[[ "$(grep -xc rsync "$CALLS")" == 1 ]]
[[ "$(grep -xc scp "$CALLS")" == 1 ]]
echo 'Ensayos del orquestador: rechazo de rutas/test/bloqueo y fallos SSH/rsync correctos.'
