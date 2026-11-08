#!/usr/bin/env bash
# Levanta Postgres, Django, Flutter web y el proxy en un solo origen (:8000).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PORT_PROXY=8000
PORT_DJANGO=8001
PORT_FLUTTER=9100

STARTED_DJANGO=false
STARTED_FLUTTER=false
STARTED_PROXY=false

load_env() {
  if [[ -f backend/.env ]]; then
    set -a
    # shellcheck disable=SC1091
    source backend/.env
    set +a
  fi
}

port_is_listening() {
  local port=$1
  if command -v ss >/dev/null 2>&1; then
    if ss -H -ltn "( sport = :${port} )" 2>/dev/null | grep -q .; then
      return 0
    fi
    return 1
  fi
  if command -v nc >/dev/null 2>&1; then
    nc -z 127.0.0.1 "$port" 2>/dev/null
    return
  fi
  echo "No encontramos ss ni nc para comprobar puertos." >&2
  return 2
}

pid_on_port() {
  local port=$1
  local pid=""
  if command -v ss >/dev/null 2>&1; then
    pid="$(ss -H -ltnp "( sport = :${port} )" 2>/dev/null | sed -n 's/.*pid=\([0-9][0-9]*\).*/\1/p' | head -n1)"
  fi
  if [[ -n "$pid" ]]; then
    echo "$pid"
    return 0
  fi
  return 1
}

process_cmdline() {
  local pid=$1
  if [[ -r "/proc/${pid}/cmdline" ]]; then
    tr '\0' ' ' <"/proc/${pid}/cmdline"
    return 0
  fi
  return 1
}

is_cody_django() {
  local cmd=$1
  [[ "$cmd" == *manage.py* && "$cmd" == *runserver* ]]
}

is_cody_proxy() {
  local cmd=$1
  [[ "$cmd" == *dev_proxy.py* ]]
}

is_cody_flutter() {
  local cmd=$1
  [[ "$cmd" == *flutter* ]] && [[ "$cmd" == *web-server* || "$cmd" == *frontend* ]]
}

ensure_port_for_service() {
  local port=$1
  local service=$2
  local matcher_name=$3

  if ! port_is_listening "$port"; then
    return 0
  fi

  local pid cmd
  if ! pid="$(pid_on_port "$port")"; then
    echo "Puerto ${port} ocupado (${service}), pero no pudimos identificar el proceso." >&2
    echo "Libére el puerto o detenga el proceso ajeno." >&2
    exit 1
  fi
  if ! cmd="$(process_cmdline "$pid")"; then
    echo "Puerto ${port} ocupado por PID ${pid} (${service}). No es de Cody; libérelo." >&2
    exit 1
  fi

  case "$matcher_name" in
    django)
      if is_cody_django "$cmd"; then
        echo "→ Django ya corre en :${port} (PID ${pid}); reutilizamos."
        return 0
      fi
      ;;
    flutter)
      if is_cody_flutter "$cmd"; then
        echo "→ Flutter web ya corre en :${port} (PID ${pid}); reutilizamos."
        return 0
      fi
      ;;
    proxy)
      if is_cody_proxy "$cmd"; then
        echo "→ Proxy ya corre en :${port} (PID ${pid}); reutilizamos."
        return 0
      fi
      ;;
  esac

  echo "Puerto ${port} ocupado por otro proceso (${service}): ${cmd}" >&2
  exit 1
}

cleanup() {
  if [[ "$STARTED_DJANGO" == true && -n "${DJANGO_PID:-}" ]]; then
    kill "$DJANGO_PID" 2>/dev/null || true
  fi
  if [[ "$STARTED_FLUTTER" == true && -n "${FLUTTER_PID:-}" ]]; then
    kill "$FLUTTER_PID" 2>/dev/null || true
  fi
  if [[ "$STARTED_PROXY" == true && -n "${PROXY_PID:-}" ]]; then
    kill "$PROXY_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

if [[ ! -x backend/.venv/bin/python ]]; then
  echo "Ejecute primero ./scripts/upgrade.sh" >&2
  exit 1
fi

load_env

echo "→ Postgres (compose)"
docker compose up -d postgres

echo "→ Esperando Postgres en :5433"
POSTGRES_READY=false
for _ in $(seq 1 30); do
  if docker compose exec -T postgres pg_isready -U "${POSTGRES_USER:-cody}" -d "${POSTGRES_DB:-cody}" >/dev/null 2>&1; then
    POSTGRES_READY=true
    break
  fi
  sleep 1
done
if [[ "$POSTGRES_READY" != true ]]; then
  echo "Postgres no respondió a tiempo. Revise: docker compose logs postgres" >&2
  exit 1
fi

# shellcheck disable=SC1091
source backend/.venv/bin/activate
export POSTGRES_HOST="${POSTGRES_HOST:-127.0.0.1}"
export POSTGRES_PORT="${POSTGRES_PORT:-5433}"

echo "→ Migraciones"
backend/.venv/bin/python backend/manage.py migrate --noinput

ensure_port_for_service "$PORT_DJANGO" "Django" django
if port_is_listening "$PORT_DJANGO"; then
  :
else
  echo "→ Django en :$PORT_DJANGO"
  backend/.venv/bin/python backend/manage.py runserver "127.0.0.1:${PORT_DJANGO}" \
    >/tmp/cody-django.log 2>&1 &
  DJANGO_PID=$!
  STARTED_DJANGO=true
  sleep 2
fi

ensure_port_for_service "$PORT_FLUTTER" "Flutter web" flutter
if port_is_listening "$PORT_FLUTTER"; then
  :
else
  echo "→ Flutter web en :$PORT_FLUTTER (la primera compilación puede tardar varios minutos)"
  (
    cd frontend
    flutter run -d web-server \
      --web-hostname=127.0.0.1 \
      --web-port="${PORT_FLUTTER}" \
      >/tmp/cody-flutter.log 2>&1
  ) &
  FLUTTER_PID=$!
  STARTED_FLUTTER=true
fi

ensure_port_for_service "$PORT_PROXY" "proxy" proxy
if port_is_listening "$PORT_PROXY"; then
  :
else
  echo "→ Proxy en :$PORT_PROXY"
  backend/.venv/bin/python scripts/dev_proxy.py --host 127.0.0.1 --port "${PORT_PROXY}" \
    >/tmp/cody-proxy.log 2>&1 &
  PROXY_PID=$!
  STARTED_PROXY=true
  sleep 1
fi

echo "→ Esperando salud de la API en http://127.0.0.1:${PORT_PROXY}/api/salud/"
API_READY=false
for _ in $(seq 1 90); do
  if curl -sf "http://127.0.0.1:${PORT_PROXY}/api/salud/" | grep -q '"base_datos":true'; then
    API_READY=true
    break
  fi
  sleep 1
done
if [[ "$API_READY" != true ]]; then
  echo "La API no respondió con salud OK en :${PORT_PROXY}. Revise /tmp/cody-django.log y /tmp/cody-proxy.log" >&2
  exit 1
fi

echo ""
echo "API lista en http://127.0.0.1:${PORT_PROXY} (mismo origen; pruebe: curl http://127.0.0.1:${PORT_PROXY}/api/salud/)"
if [[ "$STARTED_FLUTTER" == true ]] || ! curl -sf "http://127.0.0.1:${PORT_FLUTTER}/" >/dev/null 2>&1; then
  echo "La interfaz Flutter web sigue compilando o arrancando; abra http://127.0.0.1:${PORT_PROXY} cuando esté lista."
  echo "  Vea el avance en /tmp/cody-flutter.log"
else
  echo "Interfaz web: http://127.0.0.1:${PORT_PROXY}"
fi
echo "Logs: /tmp/cody-django.log, /tmp/cody-flutter.log, /tmp/cody-proxy.log"
echo "Ctrl+C detiene solo los procesos que este script inició (Postgres sigue en Docker)."

wait
