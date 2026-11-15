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
  DEMO_MODE
  NUCLEO_ADAPTADOR
  POLITICA_COBRO_VERSION
  PEDIDOS_COBRO_HABILITADO
  WAHA_INSTANCIA
  WAHA_BASE_URL
  WAHA_API_KEY
  WAHA_WEBHOOK_SECRET
)
for key in "${required[@]}"; do
  if ! grep -Eq "^[[:space:]]*${key}[[:space:]]*=[[:space:]]*[^[:space:]#]+" "$file_path"; then
    echo "Falta ${key} en ${file_var}." >&2
    exit 1
  fi
done

env_val() {
  local line
  line="$(grep -E "^[[:space:]]*$1[[:space:]]*=" "$file_path" | tail -1 || true)"
  line="${line#*=}"
  line="${line%%#*}"
  line="${line#"${line%%[![:space:]]*}"}"
  line="${line%"${line##*[![:space:]]}"}"
  printf '%s' "$line"
}

for key in "${required[@]}"; do
  if [[ -z "$(env_val "$key")" ]]; then
    echo "Falta ${key} en ${file_var}." >&2
    exit 1
  fi
done

if [[ "$(env_val NUCLEO_ADAPTADOR)" != "real" ]]; then
  echo "NUCLEO_ADAPTADOR debe ser real." >&2
  exit 1
fi
if [[ "$(env_val PEDIDOS_COBRO_HABILITADO)" != "false" ]]; then
  echo "PEDIDOS_COBRO_HABILITADO debe ser false." >&2
  exit 1
fi
demo_mode="$(env_val DEMO_MODE)"
if [[ "$demo_mode" != "true" && "$demo_mode" != "false" ]]; then
  echo "DEMO_MODE debe ser true o false." >&2
  exit 1
fi
if [[ "$demo_mode" == "true" && -z "$(env_val DEMO_PEY_BANK_ACCOUNT_ID)" ]]; then
  echo "Falta DEMO_PEY_BANK_ACCOUNT_ID para el modo demo." >&2
  exit 1
fi

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
path_var="${prefix}_DEPLOY_PATH"
if [[ "$scope" == prod && "${!path_var}" != /opt/codi/prod ]]; then
  echo "PROD_DEPLOY_PATH debe ser /opt/codi/prod." >&2
  exit 1
fi
if [[ "$scope" == test && "${!path_var}" != /opt/codi/test ]]; then
  echo "TEST_DEPLOY_PATH debe ser /opt/codi/test." >&2
  exit 1
fi


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
