#!/usr/bin/env bash
# Copia el .env de la app (variable File) y comprueba el acceso de deploy.
# Los secretos de la app van dentro del archivo, salvo OPENAI_API_KEY cuando
# GitLab la entrega como variable independiente. Host, usuario, puerto y ruta
# quedan en variables de CI. PROD_SSH_PRIVATE_KEY_V2 y TEST_SSH_PRIVATE_KEY
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
  NUCLEO_ADAPTADOR
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
if [[ "$(env_val PEDIDOS_COBRO_HABILITADO)" != "false" && "$(env_val PEDIDOS_COBRO_HABILITADO)" != "true" ]]; then
  echo "PEDIDOS_COBRO_HABILITADO debe ser true o false." >&2
  exit 1
fi
if [[ "$scope" == prod && "$(env_val WAHA_BASE_URL)" != http://127.0.0.1:3004 ]]; then
  echo "WAHA_BASE_URL de producción debe ser http://127.0.0.1:3004." >&2
  exit 1
fi
rol_web="$(env_val CODY_ROL)"
if grep -Eq '^[[:space:]]*CODY_ROL[[:space:]]*=' "$file_path" &&
  [[ "$rol_web" != web ]]; then
  echo "CODY_ROL del entorno común debe ser web o estar ausente." >&2
  exit 1
fi
stt_habilitado="$(env_val STT_HABILITADO)"
if grep -Eq '^[[:space:]]*STT_HABILITADO[[:space:]]*=' "$file_path" &&
  [[ "$stt_habilitado" != "0" && "$stt_habilitado" != "1" ]]; then
  echo "STT_HABILITADO debe ser 0 o 1." >&2
  exit 1
fi
if linea_threads="$(grep -E '^[[:space:]]*STT_CPU_THREADS[[:space:]]*=' "$file_path" | tail -1)"; then
  stt_threads="${linea_threads#*=}"
  stt_threads="${stt_threads#"${stt_threads%%[![:space:]]*}"}"
  stt_threads="${stt_threads%"${stt_threads##*[![:space:]]}"}"
  digitos_threads="${stt_threads//_/}"
  if [[ ! "$stt_threads" =~ ^[+-]?[0-9]+(_?[0-9]+)*$ || ${#digitos_threads} -gt 640 ]]; then
    echo "STT_CPU_THREADS debe ser un entero válido." >&2
    exit 1
  fi
fi
for key in DEMO_MODE POLITICA_COBRO_VERSION DEMO_PEY_BANK_ACCOUNT_ID; do
  if grep -Eq "^[[:space:]]*${key}[[:space:]]*=" "$file_path"; then
    echo "${key} ignorada; el demo es por comercio (designar_comercio_demo)." >&2
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

if [[ "$scope" == prod ]]; then
  # La llave anterior permanece revocada para que un Retry de un job viejo
  # nunca pueda desplegar con la credencial del pipeline nuevo.
  key_var=PROD_SSH_PRIVATE_KEY_V2
else
  key_var=TEST_SSH_PRIVATE_KEY
fi
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
if [[ "$scope" == prod && -n "${OPENAI_API_KEY:-}" ]] &&
  ! grep -Eq '^[[:space:]]*OPENAI_API_KEY[[:space:]]*=' "$dest"; then
  if [[ "$OPENAI_API_KEY" =~ [[:space:]] ]]; then
    echo "OPENAI_API_KEY debe ser un valor sin espacios ni saltos de línea." >&2
    exit 1
  fi
  printf '\nOPENAI_API_KEY=%s\n' "$OPENAI_API_KEY" >>"$dest"
fi

echo "Entorno ${prefix} listo. Secretos de la app en el archivo. Deploy solo en variables de CI."
