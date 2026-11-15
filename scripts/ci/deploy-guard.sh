#!/usr/bin/env bash
set -euo pipefail

mode="${1:-}"
scope="${2:-}"
dest="${3:-}"
validar() {
  [[ "$scope" == prod && "$dest" == /opt/codi/prod ]] || return 1
  [[ "$dest" != "$HOME" && ! -e "$dest/.ssh" ]] || return 1
  local ruta
  for ruta in /opt /opt/codi "$dest" "$dest/backend" \
    "$dest/backend/.env" "$dest/backend/.env.incoming" \
    "$dest/backend/.env.canal" "$dest/backend/.venv" "$dest/backend/.venv/bin" \
    "$dest/backend/staticfiles" "$dest/frontend" "$dest/landing" \
    "$dest/deploy" "$dest/scripts" "$dest/scripts/ci"; do
    [[ "$(realpath -m -- "$ruta")" == "$ruta" ]] || return 1
  done
}
validar || { echo 'Destino o scope rechazado.' >&2; exit 1; }
if [[ "$mode" == check ]]; then exit 0; fi
[[ "$mode" == lock ]] || exit 1
[[ ! -L /opt/codi/.deploy.lock ]] || exit 1
exec 9>>/opt/codi/.deploy.lock
flock -n 9 || { echo 'Ya hay un deploy en curso.' >&2; exit 1; }
validar || { echo 'Destino rechazado bajo candado.' >&2; exit 1; }
[[ ! -e /opt/codi/.maintenance ]] || { echo 'Mantenimiento activo.' >&2; exit 1; }
token="$(cat /proc/sys/kernel/random/uuid)"
printf '%s\n' "$token" > /opt/codi/.deploy.lock
printf 'READY %s\n' "$token"
read -r _ || true
