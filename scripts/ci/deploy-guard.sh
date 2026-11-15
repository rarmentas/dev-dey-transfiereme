#!/usr/bin/env bash
set -euo pipefail

mode="${1:-}"
scope="${2:-}"
dest="${3:-}"
token="${4:-}"
lock=/opt/codi/.deploy.lock
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
# Cada escritura sostiene el candado compartido y valida el token bajo él.
compartir() {
  [[ "$token" =~ ^[a-f0-9-]{36}$ && -f "$lock" && ! -L "$lock" ]] || return 1
  ! flock -n "$lock" true || return 1
  exec 9>>"$lock"
  flock -n -s 9 || return 1
  validar && [[ ! -e /opt/codi/.maintenance && "$(cat "$lock")" == "$token" ]]
}
validar || { echo 'Destino o scope rechazado.' >&2; exit 1; }
if [[ "$mode" == check ]]; then exit 0; fi
if [[ "$mode" == rsync || "$mode" == env ]]; then
  compartir || { echo 'Falta la protección del deploy.' >&2; exit 1; }
  shift 4
  if [[ "$mode" == rsync ]]; then exec rsync "$@"; fi
  umask 077
  exec cat >"$dest/backend/.env.incoming"
fi
[[ "$mode" == lock ]] || exit 1
[[ ! -L "$lock" ]] || exit 1
exec 9>>"$lock"
flock -n -x 9 || { echo 'Ya hay un deploy en curso.' >&2; exit 1; }
validar || { echo 'Destino rechazado bajo candado.' >&2; exit 1; }
[[ ! -e /opt/codi/.maintenance ]] || { echo 'Mantenimiento activo.' >&2; exit 1; }
token="$(cat /proc/sys/kernel/random/uuid)"
printf '%s\n' "$token" > "$lock"
# Pasa a compartido; la conversión no es atómica, por eso se revalida el token.
flock -n -s 9 && [[ "$(cat "$lock")" == "$token" ]] || {
  echo 'Se perdió el candado.' >&2; exit 1;
}
printf 'READY %s\n' "$token"
read -r _ || true
