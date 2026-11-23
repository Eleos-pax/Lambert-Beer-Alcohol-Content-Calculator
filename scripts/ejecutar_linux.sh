#!/usr/bin/env bash
# Inicia CalibraUV en el navegador (http://localhost:8501)
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -x .venv/bin/streamlit ]; then
  echo "Primero ejecute ./scripts/instalar_linux.sh"
  exit 1
fi
exec .venv/bin/streamlit run app.py
