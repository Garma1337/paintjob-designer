#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

VENV_PY=".venv/bin/python"

if [ ! -x "$VENV_PY" ]; then
    echo "Creating virtual environment in .venv ..."
    python3 -m venv .venv
    "$VENV_PY" -m pip install --upgrade pip
    "$VENV_PY" -m pip install -r requirements.txt
fi

exec "$VENV_PY" main.py "$@"
