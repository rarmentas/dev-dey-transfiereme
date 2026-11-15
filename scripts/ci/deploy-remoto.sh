#!/usr/bin/env bash
# Respalda y migra la base antes de detener servicios tras preflight y rsync.
set -euo pipefail
umask 077

dest="${1:-}"
python_bin="${2:-}"
service_user="${3:-}"
health_host="${4:-}"
health_port="${5:-}"
if [[ "$dest" != /opt/codi/prod || ! "$service_user" =~ ^[a-z_][a-z0-9_-]*$ ||
      ! "$health_host" =~ ^[A-Za-z0-9.-]+$ || ! "$health_port" =~ ^[0-9]+$ ]]; then
  echo 'Argumentos de deploy remoto inválidos.' >&2
  exit 2
fi
if [[ -e /run/codi-maintenance ]]; then
  echo 'CoDi está en mantenimiento.' >&2
  exit 1
fi
if [[ ! -e /run/lock/codi-deploy.lock ]] || flock -n -x /run/lock/codi-deploy.lock true; then
  echo 'Falta el bloqueo remoto del deploy.' >&2
  exit 1
fi
for path in /opt/codi "$dest" "$dest/backend" "$dest/deploy" \
  "$dest/backend/.venv" "$dest/backend/staticfiles" "$dest/backend/.env.canal" \
  "$dest/backend/.env.cobros" "$dest/backend/.env.stt"; do
  if [[ -L "$path" ]]; then echo "Enlace no permitido: $path" >&2; exit 1; fi
done
if [[ "$(realpath -e -- "$dest")" != "$dest" || ! -w "$dest" ||
      "$(systemctl show cody.service -p WorkingDirectory --value)" != "$dest/backend" ]]; then
  echo 'El destino o la unit activa no coinciden con /opt/codi/prod.' >&2
  exit 1
fi
if [[ ! -x "$python_bin" ]] ||
   [[ "$(docker inspect codi-postgres --format '{{.State.Health.Status}}' 2>/dev/null)" != healthy ]]; then
  echo 'Falta Python o PostgreSQL no está sano.' >&2
  exit 1
fi

incoming="$dest/backend/.env.incoming"
target="$dest/backend/.env"
if [[ ! -f "$incoming" || -L "$incoming" || ! -f "$target" || -L "$target" ]]; then
  echo 'Falta el entorno entrante o el entorno actual no es regular.' >&2
  exit 1
fi

env_val() {
  local key="$1" line
  line="$(grep -E "^[[:space:]]*${key}[[:space:]]*=" "$incoming" | tail -1 || true)"
  line="${line#*=}"
  line="${line%%#*}"
  line="${line#"${line%%[![:space:]]*}"}"
  line="${line%"${line##*[![:space:]]}"}"
  printf '%s' "$line"
}
if [[ "$(env_val POSTGRES_PORT)" != 5435 ]]; then
  echo 'POSTGRES_PORT debe ser 5435.' >&2
  exit 1
fi

[[ "$(env_val WAHA_BASE_URL)" == http://127.0.0.1:3004 ]] || {
  echo "WAHA_BASE_URL de producción debe ser http://127.0.0.1:3004." >&2; exit 1;
}
stt_habilitado="$(env_val STT_HABILITADO)"
if ! grep -Eq '^[[:space:]]*STT_HABILITADO[[:space:]]*=' "$incoming"; then
  stt_habilitado=0
fi
[[ "$stt_habilitado" == 0 || "$stt_habilitado" == 1 ]] || {
  echo "STT_HABILITADO debe ser 0 o 1." >&2; exit 1;
}
if linea_threads="$(grep -E '^[[:space:]]*STT_CPU_THREADS[[:space:]]*=' "$incoming" | tail -1)"; then
  stt_threads="${linea_threads#*=}"
  stt_threads="${stt_threads#"${stt_threads%%[![:space:]]*}"}"
  stt_threads="${stt_threads%"${stt_threads##*[![:space:]]}"}"
  digitos_threads="${stt_threads//_/}"
  if [[ ! "$stt_threads" =~ ^[+-]?[0-9]+(_?[0-9]+)*$ || ${#digitos_threads} -gt 640 ]]; then
    echo "STT_CPU_THREADS debe ser un entero válido." >&2
    exit 1
  fi
fi
rol_web="$(env_val CODY_ROL)"
if grep -Eq '^[[:space:]]*CODY_ROL[[:space:]]*=' "$incoming" && [[ "$rol_web" != web ]]; then
  echo "CODY_ROL del entorno común debe ser web." >&2; exit 1
fi
stt_home=/var/lib/codi/stt

backup_dir="$(mktemp -d)"
unit_tmp="$backup_dir/cody.service"
committed=0
stopped=0
backup_partial=""
# shellcheck disable=SC2329 # Invocada por trap EXIT.
cleanup() {
  local result=$?
  trap - EXIT
  if (( result != 0 && stopped && ! committed )); then
    echo 'El arranque falló; restaurando units y entornos previos.' >&2
    for rol in canal cobros stt; do
      sudo -n systemctl stop "cody-$rol.service" || true
      if [[ ! -f "$backup_dir/$rol.enabled" ]]; then
        sudo -n systemctl disable "cody-$rol.service" || true
      fi
      if [[ -f "$backup_dir/cody-$rol.service.previous" ]]; then
        sudo -n install -m 644 "$backup_dir/cody-$rol.service.previous" \
          "/etc/systemd/system/cody-$rol.service" || true
      else
        sudo -n rm -f -- "/etc/systemd/system/cody-$rol.service" || true
      fi
      if [[ -f "$backup_dir/.env.$rol" ]]; then
        install -m 600 "$backup_dir/.env.$rol" "$dest/backend/.env.$rol" || true
      else
        rm -f -- "$dest/backend/.env.$rol"
      fi
    done
    sudo -n install -m 644 "$backup_dir/cody.service.previous" /etc/systemd/system/cody.service || true
    install -m 600 "$backup_dir/.env" "$target" || true
    sudo -n systemctl daemon-reload || true
    web_recuperada=1
    if ! sudo -n systemctl restart cody.service; then
      if ! sudo -n systemctl start cody.service; then
        web_recuperada=0
      fi
    fi
    if ! sudo -n systemctl is-active cody.service; then
      web_recuperada=0
    fi
    if [[ "$web_recuperada" != 1 ]]; then
      echo 'recuperación web fallida; requiere intervención de operación.' >&2
    fi
    for rol in canal cobros stt; do
      if [[ -f "$backup_dir/$rol.enabled" ]]; then
        sudo -n systemctl enable "cody-$rol.service" || true
      fi
      if [[ -f "$backup_dir/$rol.active" ]]; then
        sudo -n systemctl start "cody-$rol.service" || true
      fi
    done
  fi
  if [[ -n "$backup_partial" ]]; then rm -f -- "$backup_partial"; fi
  rm -f -- "$incoming" "$unit_tmp"
  rm -rf -- "$backup_dir"
  exit "$result"
}
trap cleanup EXIT

# Cargar solo claves de entorno válidas, con valores escapados por shlex.
# No se imprime el archivo ni las exportaciones.
eval "$("$python_bin" -c '
import shlex
import sys
from pathlib import Path

for raw in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    line = raw.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    key = key.strip()
    if not key or not (key[0].isalpha() or key[0] == "_"):
        continue
    if not all(c.isalnum() or c == "_" for c in key):
        continue
    print(f"export {key}={shlex.quote(value.strip())}")
' "$incoming")"

respaldar_base() {
  local carpeta archivo tmp tamano f
  local -a respaldos
  if [[ ! "${POSTGRES_USER:-}" =~ ^[A-Za-z0-9_][A-Za-z0-9_.-]*$ ||
        ! "${POSTGRES_DB:-}" =~ ^[A-Za-z0-9_][A-Za-z0-9_.-]*$ ]]; then
    echo 'Respaldo fallido: usuario o base de PostgreSQL inválidos.' >&2
    return 1
  fi
  if [[ "${POSTGRES_HOST:-}" != 127.0.0.1 && "${POSTGRES_HOST:-}" != localhost ]]; then
    echo 'Respaldo fallido: POSTGRES_HOST debe ser local.' >&2
    return 1
  fi
  if [[ -z "${HOME:-}" ]]; then
    echo 'Respaldo fallido: HOME no está definido.' >&2
    return 1
  fi
  carpeta="${HOME:?}/respaldos/codi"
  if ! mkdir -p -- "$carpeta" || ! chmod 700 "$carpeta"; then
    echo 'Respaldo fallido: no se pudo preparar el directorio.' >&2
    return 1
  fi
  archivo="$carpeta/codi-pre-deploy-$(date +%Y%m%d-%H%M%S).dump"
  if [[ -e "$archivo" ]] || ! tmp="$(mktemp "${archivo}.XXXXXX.partial")"; then
    echo 'Respaldo fallido: no se pudo crear un archivo nuevo.' >&2
    return 1
  fi
  backup_partial="$tmp"
  if [[ -n "${POSTGRES_PASSWORD:-}" ]]; then
    if ! PGPASSWORD="$POSTGRES_PASSWORD" docker exec -e PGPASSWORD codi-postgres \
      pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB" >"$tmp" 2>/dev/null; then
      rm -f -- "$tmp"
      echo 'Respaldo fallido: pg_dump no terminó correctamente.' >&2
      return 1
    fi
  elif ! env -u PGPASSWORD docker exec codi-postgres pg_dump -U "$POSTGRES_USER" \
    -Fc "$POSTGRES_DB" >"$tmp" 2>/dev/null; then
    rm -f -- "$tmp"
    echo 'Respaldo fallido: pg_dump no terminó correctamente.' >&2
    return 1
  fi
  if ! test -s "$tmp" || ! docker exec -i codi-postgres pg_restore --list <"$tmp" >/dev/null 2>&1 ||
     ! mv -n -- "$tmp" "$archivo" || [[ -e "$tmp" ]]; then
    rm -f -- "$tmp"
    echo 'Respaldo fallido: el archivo está vacío, es inválido o no se pudo guardar.' >&2
    return 1
  fi
  backup_partial=""
  tamano="$(wc -c < "$archivo")"
  printf 'Respaldo: %s (%s bytes)\n' "$archivo" "$tamano"
  # Solo archivos regulares con el nombre temporal exacto, ordenados por nombre.
  local LC_ALL=C
  shopt -s nullglob
  respaldos=()
  for f in "$carpeta"/codi-pre-deploy-*.dump; do
    if [[ -f "$f" && ! -L "$f" && "${f##*/}" =~ ^codi-pre-deploy-[0-9]{8}-[0-9]{6}\.dump$ ]]; then
      respaldos+=("$f")
    fi
  done
  shopt -u nullglob
  while (( ${#respaldos[@]} > 10 )); do
    f="${respaldos[0]}"
    rm -f -- "$f"
    respaldos=("${respaldos[@]:1}")
  done
}

if [[ ! -x "$dest/backend/.venv/bin/python" ]]; then
  "$python_bin" -m venv "$dest/backend/.venv"
fi
"$dest/backend/.venv/bin/pip" install --disable-pip-version-check --no-input -r "$dest/backend/requirements-canal.txt"
(
  cd "$dest/backend"
  ./.venv/bin/python manage.py check
)
# Verificar configuración, units y STT antes del respaldo y las migraciones.
# Preparar units y entornos por rol antes de detener servicios.
for suffix in "" "-canal" "-cobros" "-stt"; do
  unit_tmp="$backup_dir/cody${suffix}.service"
  sed -e "s|@DEPLOY_PATH@|$dest|g" -e "s|@DEPLOY_USER@|$service_user|g" \
    -e 's|@UNIT_BASE@|cody|g' -e "s|@STT_HOME@|$stt_home|g" \
    "$dest/deploy/cody${suffix}.service.in" >"$unit_tmp"
  if grep -Eq '@[A-Z_]+@|/\.\.?(/|[[:space:]]|$)' "$unit_tmp" || \
     sed -E "s|$dest(/| |$)|\\1|g" "$unit_tmp" | grep -q '/opt/codi'; then
    echo 'La unit contiene marcadores o rutas no permitidas.' >&2; exit 1
  fi
  grep -Fxq "WorkingDirectory=$dest/backend" "$unit_tmp"
  if [[ "$suffix" == -stt ]]; then
    grep -Fxq "ReadWritePaths=$dest $stt_home" "$unit_tmp"
  else
    grep -Fxq "ReadWritePaths=$dest" "$unit_tmp"
  fi
  if [[ "$suffix" != -stt || "$stt_habilitado" == 1 ]]; then
    systemd-analyze verify "$unit_tmp" >/dev/null
  fi
done
grep -Fxq "EnvironmentFile=$dest/backend/.env" "$backup_dir/cody.service"
grep -Fq "ExecStart=$dest/backend/.venv/bin/gunicorn " "$backup_dir/cody.service"
grep -Fxq "RuntimeDirectory=cody" "$backup_dir/cody.service"
grep -Fq -- "--pid /run/cody/gunicorn.pid" "$backup_dir/cody.service"
for rol in canal cobros stt; do
  grep -Fxq "EnvironmentFile=$dest/backend/.env.$rol" "$backup_dir/cody-$rol.service"
  grep -Eq "^Environment=CODY_ROL=$rol( |$)" "$backup_dir/cody-$rol.service"
done
grep -Fxq "ExecStart=$dest/backend/.venv/bin/python manage.py procesar_canal" "$backup_dir/cody-canal.service"
grep -Fxq "ExecStart=$dest/backend/.venv/bin/python manage.py procesar_cobros" "$backup_dir/cody-cobros.service"
grep -Fxq "ExecStart=$stt_home/venv/bin/python manage.py procesar_audio" "$backup_dir/cody-stt.service"
grep -Fxq "Environment=CODY_ROL=stt HF_HOME=$stt_home/modelos HF_HUB_OFFLINE=1" "$backup_dir/cody-stt.service"
# Las listas permitidas evitan propagar secretos o sobrescribir CODY_ROL.
comunes='POSTGRES_DB|POSTGRES_USER|POSTGRES_PASSWORD|POSTGRES_HOST|POSTGRES_PORT|DJANGO_SECRET_KEY|DEBUG|ALLOWED_HOSTS|DEMO_MODE|DEMO_PEY_BANK_ACCOUNT_ID|NUCLEO_ADAPTADOR|POLITICA_COBRO_VERSION|PEDIDOS_COBRO_HABILITADO'
canal_claves="$comunes|WAHA_INSTANCIA|WAHA_BASE_URL|WAHA_API_KEY|STT_HABILITADO|STT_MODELO|STT_CPU_THREADS"
cobros_claves="$comunes|PEY_API_KEY|PEY_ADAPTADOR"
grep -E "^[[:space:]]*($canal_claves)[[:space:]]*=" "$incoming" >"$backup_dir/env.canal" || [[ "$?" -eq 1 ]]
cp "$backup_dir/env.canal" "$backup_dir/env.stt"
grep -E "^[[:space:]]*($cobros_claves)[[:space:]]*=" "$incoming" >"$backup_dir/env.cobros" || [[ "$?" -eq 1 ]]

chmod 600 "$backup_dir/env.canal" "$backup_dir/env.cobros" "$backup_dir/env.stt"
if [[ "$stt_habilitado" == 1 ]]; then
  for ruta in /var /var/lib /var/lib/codi "$stt_home" "$stt_home/venv" \
    "$stt_home/venv/bin" "$stt_home/modelos"; do
    [[ "$(realpath -m -- "$ruta")" == "$ruta" ]] || {
      echo "Ruta STT rechazada." >&2; exit 1;
    }
  done
  [[ -d "$stt_home/modelos" && -r "$stt_home/modelos" && -x "$stt_home/modelos" &&
     -w "$stt_home" && -x "$stt_home/venv/bin/python" ]] || {
    echo "Faltan venv, caché o permisos STT; consulte a operación." >&2; exit 1;
  }
  command -v ffmpeg >/dev/null && command -v ffprobe >/dev/null || {
    echo "Faltan ffmpeg o ffprobe." >&2; exit 1;
  }
  disponible="$(df -Pk "$stt_home" | awk 'NR==2 {print $4}')"
  [[ "$disponible" =~ ^[0-9]+$ && "$disponible" -ge 524288 ]] || {
    echo "Espacio insuficiente para STT." >&2; exit 1;
  }
  if ! (cd "$dest/backend" && env -i PATH="$PATH" HOME="$stt_home" \
      HF_HOME="$stt_home/modelos" HF_HUB_OFFLINE=1 CODY_ROL=stt \
      DJANGO_SETTINGS_MODULE=config.settings "$stt_home/venv/bin/python" - \
      "$backup_dir/env.stt" <<'PYSTT'
import os
import sys
from pathlib import Path
from importlib.metadata import version

for linea in Path(sys.argv[1]).read_text().splitlines():
    if "=" in linea:
        clave, valor = linea.split("=", 1)
        os.environ[clave.strip()] = valor.strip()
import django
import numpy
import faster_whisper

if version("faster-whisper") != "1.1.1" or version("numpy") != "2.2.4":
    raise RuntimeError("versiones STT distintas de los requisitos")
django.setup()
from canales.stt import FasterWhisperTranscriptor
FasterWhisperTranscriptor().precargar()
PYSTT
  ); then
    echo "Dependencias o modelo STT no disponibles offline; consulte a operación." >&2
    exit 1
  fi
fi


# Respaldar y migrar solo después de validar la configuración entrante.
respaldar_base
(
  cd "$dest/backend"
  ./.venv/bin/python manage.py migrate --plan | awk '/^[A-Za-z0-9_]+\.[A-Za-z0-9_]+$/'
  ./.venv/bin/python manage.py migrate --noinput
  ./.venv/bin/python manage.py migrate --check --noinput
  ./.venv/bin/python manage.py collectstatic --noinput
)
chmod -R u+rwX,go-rwx "$dest/backend/.venv"
chmod -R u+rwX,go+rX,go-w "$dest/backend/staticfiles"

cp -p /etc/systemd/system/cody.service "$backup_dir/cody.service.previous"
cp -p "$target" "$backup_dir/.env"
for rol in canal cobros stt; do
  if [[ -f "/etc/systemd/system/cody-$rol.service" ]]; then
    cp -p "/etc/systemd/system/cody-$rol.service" "$backup_dir/cody-$rol.service.previous"
  fi
  if [[ -f "$dest/backend/.env.$rol" ]]; then
    cp -p "$dest/backend/.env.$rol" "$backup_dir/.env.$rol"
  fi
  if systemctl is-active --quiet "cody-$rol.service"; then
    touch "$backup_dir/$rol.active"
  fi
  if systemctl is-enabled --quiet "cody-$rol.service"; then
    touch "$backup_dir/$rol.enabled"
  fi
done
sudo -n true
stopped=1
for rol in cobros canal stt; do
  if [[ -f "$backup_dir/$rol.active" ]]; then
    sudo -n systemctl stop "cody-$rol.service"
  fi
done
sudo -n systemctl stop cody.service
install -m 600 "$incoming" "$target"
for rol in canal cobros stt; do
  install -m 600 "$backup_dir/env.$rol" "$dest/backend/.env.$rol"
done
for suffix in "" "-canal" "-cobros" "-stt"; do
  sudo -n install -m 644 "$backup_dir/cody${suffix}.service" "/etc/systemd/system/cody${suffix}.service"
done
sudo -n systemctl daemon-reload
sudo -n systemctl start cody.service

for _ in $(seq 1 30); do
  code="$(curl -sS --max-time 2 -o /dev/null -w '%{http_code}' \
    -H "Host: $health_host" "http://127.0.0.1:$health_port/api/salud/" 2>/dev/null || true)"
  if [[ "$code" == 200 ]]; then
    break
  fi
  sleep 1
done
if [[ "$code" != 200 ]]; then
  echo 'CoDi no respondió 200 tras el arranque.' >&2
  exit 1
fi

inicio_canal="$("$dest/backend/.venv/bin/python" -c \
  'from datetime import datetime, timezone; print(datetime.now(timezone.utc).isoformat())')"
sudo -n systemctl restart cody-cobros.service
sudo -n systemctl restart cody-canal.service
if [[ "$stt_habilitado" == 1 ]]; then
  sudo -n systemctl enable --now cody-stt.service
else
  sudo -n systemctl disable --now cody-stt.service
fi
procesos=(procesar_cobros procesar_canal)
units=(cody-cobros.service cody-canal.service)
if [[ "$stt_habilitado" == 1 ]]; then
  procesos+=(procesar_audio)
  units+=(cody-stt.service)
fi
for i in "${!procesos[@]}"; do
  listo=0
  for _ in $(seq 1 30); do
    if (cd "$dest/backend" && ./.venv/bin/python manage.py estado_canal \
        --proceso "${procesos[$i]}" --max-edad 30 --desde "$inicio_canal") && \
       systemctl is-active --quiet "${units[$i]}"; then
      listo=1; break
    fi
    sleep 1
  done
  if [[ "$listo" != 1 ]]; then
    echo "El proceso ${procesos[$i]} no registró un latido reciente o está inactivo." >&2
    exit 1
  fi
done
sudo -n systemctl enable cody-cobros.service cody-canal.service
committed=1
echo 'CoDi y workers sanos en /opt/codi/prod; PostgreSQL no se recreó.'
