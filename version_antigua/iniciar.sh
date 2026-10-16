#!/usr/bin/env bash
# ============================================================
#  Ciudad Inteligente - Cajamarca  |  VERSION ANTIGUA
#  (codigo monolitico, sin SOLID)  ·  Linux / macOS
#  Uso:  ./iniciar.sh   (o:  bash iniciar.sh)
# ============================================================
set -euo pipefail
cd "$(dirname "$0")"

echo "============================================================"
echo "   Ciudad Inteligente - Cajamarca  |  VERSION ANTIGUA"
echo "   (codigo monolitico, sin SOLID)"
echo "============================================================"

PY="python3"
if ! command -v python3 >/dev/null 2>&1; then
    PY="python"
fi
if ! command -v "$PY" >/dev/null 2>&1; then
    echo "[ERROR] No se encontro Python. Instala Python 3.10+."
    exit 1
fi

VENV_PY=".venv/bin/python"

if [ ! -x "$VENV_PY" ]; then
    echo "[1/4] Creando entorno virtual (.venv)..."
    "$PY" -m venv .venv
else
    echo "[1/4] Entorno virtual ya existe."
fi

echo "[2/4] Instalando dependencias..."
"$VENV_PY" -m pip install --disable-pip-version-check -q -r requirements.txt

if [ ! -f "data/users.json" ]; then
    echo "[3/4] Creando usuarios de prueba..."
    "$VENV_PY" seed_users.py
else
    echo "[3/4] Usuarios de prueba ya existen."
fi

export PORT=5001
echo "[4/4] Iniciando servidor en http://127.0.0.1:5001 (Ctrl+C para detener)"
exec "$VENV_PY" app.py
