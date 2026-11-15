#!/usr/bin/env bash
# Se envía por stdin antes de rsync; no depende de archivos del release remoto.
set -euo pipefail

dest="${1:-}"
service_user="${2:-}"
python_bin="${3:-}"
if [[ "$dest" != /opt/codi/prod ]]; then
  echo 'Destino remoto rechazado.' >&2
  exit 2
fi
if [[ -e /run/codi-maintenance ]]; then
  echo 'CoDi está en mantenimiento.' >&2
  exit 1
fi
for path in /opt/codi "$dest" "$dest/backend" "$dest/frontend" "$dest/landing" \
  "$dest/deploy" "$dest/scripts" "$dest/backend/.venv" \
  "$dest/backend/.env" "$dest/backend/.env.incoming" \
  "$dest/backend/staticfiles"; do
  if [[ -L "$path" ]]; then echo "Enlace no permitido: $path" >&2; exit 1; fi
done
if find "$dest" -path "$dest/backend/.venv" -prune -o -type l -print -quit | grep -q .; then
  echo 'El release contiene un enlace fuera del venv; revisar antes de rsync.' >&2
  exit 1
fi
if [[ "$(realpath -e -- "$dest")" != "$dest" || ! -d "$dest" || ! -w "$dest" ]]; then
  echo 'El destino real debe existir y ser escribible.' >&2
  exit 1
fi
if [[ "$(stat -c %U "$dest")" != "$service_user" ]]; then
  echo 'El propietario del destino no coincide con el usuario de deploy.' >&2
  exit 1
fi
if [[ ! -f "$dest/backend/.env" || ! -x "$python_bin" ]]; then
  echo 'Falta el entorno instalado o el intérprete Python.' >&2
  exit 1
fi
if [[ "$(systemctl show cody.service -p WorkingDirectory --value)" != "$dest/backend" ]] ||
   ! systemctl is-active --quiet cody.service; then
  echo 'La unit activa todavía no apunta a /opt/codi/prod.' >&2
  exit 1
fi
if [[ "$(docker inspect codi-postgres --format '{{.State.Running}}' 2>/dev/null)" != true ]] ||
   [[ "$(docker inspect codi-postgres --format '{{.State.Health.Status}}' 2>/dev/null)" != healthy ]] ||
   [[ "$(docker inspect codi-postgres --format '{{index .Config.Labels "com.docker.compose.project"}}' 2>/dev/null)" != codi ]] ||
   [[ "$(docker inspect codi-postgres --format '{{index .Config.Labels "com.docker.compose.service"}}' 2>/dev/null)" != postgres ]]; then
  echo 'PostgreSQL productivo no coincide con el inventario o no está sano.' >&2
  exit 1
fi
if ! ss -ltnH '( sport = :5435 )' | grep -q '127.0.0.1:5435'; then
  echo 'PostgreSQL no publica 127.0.0.1:5435.' >&2
  exit 1
fi
echo 'Preflight remoto correcto; destino limitado a /opt/codi/prod.'
