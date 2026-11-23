#!/usr/bin/env bash
# Starts CalibraUV in the browser (http://localhost:8501)
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -x .venv/bin/streamlit ]; then
  echo "Run ./scripts/install_linux.sh first"
  exit 1
fi
exec .venv/bin/streamlit run app.py "$@"
