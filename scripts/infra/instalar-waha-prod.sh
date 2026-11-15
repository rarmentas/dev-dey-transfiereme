#!/usr/bin/env bash
# Alta inicial independiente de WAHA. Ejecutar en el VPS tras aceptar CoDi en prod.
set -euo pipefail
umask 077

source_compose="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/deploy/waha-prod/compose.yaml"
target=/opt/codi/waha-prod
state=/var/lib/codi/waha-prod
image='devlikeapro/waha@sha256:1f7faeb0227ad5edb5711f7058bfce807ea65e5f92234af0778e4db140f6eb46'
project=codi-waha-prod
service=waha
container=codi-waha-prod

if [[ -L /opt/codi || -L /opt/codi/prod ||
      "$(realpath -e /opt/codi/prod 2>/dev/null)" != /opt/codi/prod ||
      -e "$target" || -L "$target" || -e "$state" || -L "$state" ]]; then
  echo 'Destino WAHA ya existe o es un enlace; revisar antes de instalar.' >&2
  exit 1
fi
if ! systemctl is-active --quiet cody.service ||
   [[ "$(systemctl show cody.service -p WorkingDirectory --value)" != /opt/codi/prod/backend ]]; then
  echo 'Primero debe estar aceptada la migración de CoDi a /opt/codi/prod.' >&2
  exit 1
fi
if [[ -n "$(ss -ltnH '( sport = :3004 )')" ]] ||
   docker ps -a --format '{{.Names}}' | grep -Fxq "$container" ||
   docker ps -a --filter "label=com.docker.compose.project=$project" --format '{{.ID}}' | grep -q . ||
   docker ps -a --format '{{.Ports}}' | grep -q '3004'; then
  echo 'Puerto 3004 o nombre de contenedor ocupado.' >&2
  exit 1
fi
if [[ "$(docker image inspect "$image" --format '{{.Architecture}}' 2>/dev/null)" != amd64 ]]; then
  echo 'La imagen WAHA fijada no está disponible para amd64; preparar la imagen antes del corte.' >&2
  exit 1
fi
if [[ "$(docker inspect codi-postgres --format '{{.State.Health.Status}}' 2>/dev/null)" != healthy ]]; then
  echo 'PostgreSQL de CoDi no está sano.' >&2
  exit 1
fi
pg_before="$(docker inspect codi-postgres --format '{{.Id}}|{{.State.StartedAt}}|{{.Image}}')"

owner="$(id -un)"
group="$(id -gn)"
sudo -n install -d -o "$owner" -g "$group" -m 750 "$target"
sudo -n install -d -o "$owner" -g "$group" -m 750 "$state"
sudo -n install -d -o "$owner" -g "$group" -m 700 "$state/sessions" "$state/media"
install -m 640 "$source_compose" "$target/compose.yaml"
openssl rand -hex 32 >"$target/.api-key"
chmod 600 "$target/.api-key"
key_hash="$(tr -d '\n' <"$target/.api-key" | sha512sum)"
key_hash="${key_hash%% *}"
{
  printf 'WAHA_API_KEY=sha512:%s\n' "$key_hash"
  printf '%s\n' 'WAHA_DASHBOARD_ENABLED=false' 'WHATSAPP_SWAGGER_ENABLED=false' \
    'WAHA_PRINT_QR=False' 'WHATSAPP_DEFAULT_ENGINE=GOWS' \
    'WAHA_MEDIA_STORAGE=LOCAL' 'WHATSAPP_FILES_FOLDER=/app/.media' \
    'WHATSAPP_FILES_LIFETIME=0'
} >"$target/.env"
chmod 600 "$target/.env"

compose=(docker compose --project-name "$project" --env-file "$target/.env" -f "$target/compose.yaml")
"${compose[@]}" config --quiet
started=0
cleanup() {
  local result=$?
  trap - EXIT
  if (( result != 0 && started )); then
    echo 'WAHA no pasó la comprobación; deteniendo solo codi-waha-prod.' >&2
    "${compose[@]}" stop "$service" || true
  fi
  exit "$result"
}
trap cleanup EXIT

started=1
"${compose[@]}" up -d --no-deps --no-build --pull never "$service"
code_no_key=""
code_wrong=""
code_right=""
for _ in $(seq 1 30); do
  if [[ "$(docker inspect "$container" --format '{{.State.Running}}' 2>/dev/null)" == true ]]; then
    code_no_key="$(curl -sS --max-time 2 -o /dev/null -w '%{http_code}' \
      http://127.0.0.1:3004/api/sessions 2>/dev/null || true)"
    code_wrong="$(curl -sS --max-time 2 -o /dev/null -w '%{http_code}' \
      -H 'X-Api-Key: invalid-key' http://127.0.0.1:3004/api/sessions 2>/dev/null || true)"
    code_right="$(printf 'header = "X-Api-Key: %s"\n' "$(cat "$target/.api-key")" |
      curl -sS --max-time 2 -K - -o /dev/null -w '%{http_code}' \
        http://127.0.0.1:3004/api/sessions 2>/dev/null || true)"
    if [[ "$code_no_key" == 401 && "$code_wrong" == 401 && "$code_right" == 200 ]]; then
      break
    fi
  fi
  sleep 2
done
if [[ "$code_no_key" != 401 || "$code_wrong" != 401 || "$code_right" != 200 ]]; then
  echo 'WAHA no superó las pruebas de autenticación.' >&2
  exit 1
fi
if [[ "$(docker inspect codi-postgres --format '{{.Id}}|{{.State.StartedAt}}|{{.Image}}')" != "$pg_before" ]]; then
  echo 'PostgreSQL cambió durante la instalación WAHA.' >&2
  exit 1
fi
if [[ "$(docker inspect "$container" --format '{{.Config.Image}}')" != "$image" ]]; then
  echo 'La imagen del contenedor no coincide con el digest fijado.' >&2
  exit 1
fi
if [[ "$(docker port "$container" 3000/tcp 2>/dev/null)" != 127.0.0.1:3004 ]]; then
  echo 'WAHA no está limitado a loopback.' >&2
  exit 1
fi
mounts="$(docker inspect "$container" --format '{{range .Mounts}}{{.Source}}:{{.Destination}};{{end}}')"
if [[ "$mounts" != *'/var/lib/codi/waha-prod/sessions:/app/.sessions;'* ||
      "$mounts" != *'/var/lib/codi/waha-prod/media:/app/.media;'* ]] ||
   ! docker exec "$container" sh -c 'test -w /app/.sessions && test -w /app/.media'; then
  echo 'Los binds de WAHA no son los esperados o no permiten escritura.' >&2
  exit 1
fi
if [[ "$(docker inspect "$container" --format '{{.HostConfig.Memory}}|{{.HostConfig.NanoCpus}}')" != '1073741824|1000000000' ]]; then
  echo 'WAHA no conserva los límites de memoria y CPU previstos.' >&2
  exit 1
fi
code_codi="$(curl -sS --max-time 5 -o /dev/null -w '%{http_code}' \
  -H 'Host: transfiereme.asware.com.mx' http://127.0.0.1:8000/api/salud/ 2>/dev/null || true)"
if [[ "$code_codi" != 200 ]]; then
  echo 'CoDi no está sano tras instalar WAHA.' >&2
  exit 1
fi
echo 'WAHA de CoDi instalado: 127.0.0.1:3004, API autenticada, datos persistentes.'
