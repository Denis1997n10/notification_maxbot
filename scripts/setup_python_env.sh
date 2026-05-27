#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-.venv}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "[setup_python_env] python3 not found" >&2
  exit 1
fi

$PYTHON_BIN -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip
pip install -r backend/requirements-dev.txt

echo "[setup_python_env] done. activate with: source $VENV_DIR/bin/activate"
