#!/usr/bin/env bash
# Prepara el entorno local: venv Python 3.12, dependencias y Flutter pub get.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v python3.12 >/dev/null 2>&1; then
  echo "Se requiere Python 3.12 (comando python3.12 en PATH). Instálelo y vuelva a ejecutar." >&2
  exit 1
fi
PYTHON=python3.12

if [[ ! -d backend/.venv ]]; then
  if command -v uv >/dev/null 2>&1; then
    uv venv backend/.venv --python "$PYTHON"
  else
    "$PYTHON" -m venv backend/.venv
  fi
fi
VENV_PY="$ROOT/backend/.venv/bin/python"
if [[ ! -x "$VENV_PY" ]]; then
  echo "No se pudo crear backend/.venv" >&2
  exit 1
fi
if "$VENV_PY" -m pip --version >/dev/null 2>&1; then
  "$VENV_PY" -m pip install --upgrade pip
  "$VENV_PY" -m pip install -r backend/requirements.txt
elif command -v uv >/dev/null 2>&1; then
  uv pip install -r backend/requirements.txt --python "$VENV_PY"
else
  echo "Instale pip en el venv o instale uv." >&2
  exit 1
fi

if ! command -v flutter >/dev/null 2>&1; then
  echo "Flutter no está en PATH. Instale Flutter 3.47.x (ver docs/stack-tecnologico/000-stack.md)." >&2
  exit 1
fi

cd frontend
flutter pub get
cd "$ROOT"

if [[ ! -f backend/.env ]]; then
  echo "Copie backend/.env.example a backend/.env y ajuste valores locales si hace falta."
fi

echo "Listo. Siguiente paso: ./scripts/dev-start.sh"
