#!/usr/bin/env bash
# Copia el .env de la app (variable File) y comprueba el acceso de deploy.
# Los secretos de la app van dentro del archivo. Host, usuario, puerto y ruta
# quedan en variables de CI. PROD_SSH_PRIVATE_KEY y TEST_SSH_PRIVATE_KEY
# llegan en base64 y se decodifican a un archivo temporal. Nada de eso se
# copia a backend/.env. No imprime valores.
# Uso: bash scripts/ci-install-env.sh prod|test [destino]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

scope="${1:-}"
case "$scope" in
  prod) prefix="PROD" ;;
  test) prefix="TEST" ;;
  *)
    echo "Indique prod o test." >&2
    exit 2
    ;;
esac

file_var="${prefix}_ENV_FILE"
file_path="${!file_var:-}"
if [[ -z "$file_path" || ! -f "$file_path" ]]; then
  echo "Defina la variable File ${file_var}. GitLab debe entregar la ruta de un archivo." >&2
  exit 1
fi

if grep -Eq 'PRIVATE KEY|^([[:space:]]*)(DEPLOY_HOST|DEPLOY_USER|DEPLOY_PORT|DEPLOY_PATH|SSH_PRIVATE_KEY)[[:space:]]*=' "$file_path"; then
  echo "El archivo ${file_var} no debe traer datos de deploy ni la llave SSH." >&2
  exit 1
fi

required=(
  POSTGRES_DB
  POSTGRES_USER
  POSTGRES_PASSWORD
  POSTGRES_HOST
  POSTGRES_PORT
  DJANGO_SECRET_KEY
  DEBUG
  ALLOWED_HOSTS
  WEBHOOK_BASE_URL
  PEY_API_KEY
  PEY_WEBHOOK_SECRET
)
for key in "${required[@]}"; do
  if ! grep -Eq "^[[:space:]]*${key}[[:space:]]*=[[:space:]]*[^[:space:]#]+" "$file_path"; then
    echo "Falta ${key} en ${file_var}." >&2
    exit 1
  fi
done

require_ci() {
  local ci_var="$1"
  if [[ -z "${!ci_var:-}" ]]; then
    echo "Defina la variable de CI ${ci_var}." >&2
    exit 1
  fi
}

require_ci "${prefix}_DEPLOY_HOST"
require_ci "${prefix}_DEPLOY_USER"
require_ci "${prefix}_DEPLOY_PATH"
require_ci "${prefix}_DEPLOY_PORT"

port_var="${prefix}_DEPLOY_PORT"
if ! [[ "${!port_var}" =~ ^[0-9]+$ ]]; then
  echo "${port_var} debe ser un número de puerto." >&2
  exit 1
fi

key_var="${prefix}_SSH_PRIVATE_KEY"
key_b64="${!key_var:-}"
key_b64="${key_b64//[[:space:]]/}"
if [[ -z "$key_b64" ]]; then
  echo "Defina la variable de CI ${key_var} con la llave privada en base64." >&2
  exit 1
fi
key_path="$(mktemp)"
chmod 600 "$key_path"
if ! printf '%s' "$key_b64" | base64 -d >"$key_path" 2>/dev/null; then
  rm -f "$key_path"
  echo "${key_var} no es base64 válido." >&2
  exit 1
fi
if ! grep -q "PRIVATE KEY" "$key_path"; then
  rm -f "$key_path"
  echo "${key_var} no decodifica a una llave privada." >&2
  exit 1
fi
export SSH_PRIVATE_KEY_FILE="$key_path"

dest="${2:-$ROOT/backend/.env}"
umask 077
cp "$file_path" "$dest"
chmod 600 "$dest"

echo "Entorno ${prefix} listo. Secretos de la app en el archivo. Deploy solo en variables de CI."
