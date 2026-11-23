#!/usr/bin/env bash
# Starts CalibraUV in the browser (http://localhost:8501)
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -x .venv/bin/streamlit ]; then
  echo "Run ./scripts/install_linux.sh first"
  exit 1
fi
# Skip Streamlit's one-time e-mail prompt (no data is sent)
if [ ! -f "$HOME/.streamlit/credentials.toml" ]; then
  mkdir -p "$HOME/.streamlit"
  printf '[general]\nemail = ""\n' > "$HOME/.streamlit/credentials.toml"
fi
exec .venv/bin/streamlit run app.py "$@"
