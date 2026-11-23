#!/usr/bin/env bash
# Uninstalls CalibraUV: removes its virtual environment, caches and settings,
# and optionally the whole application folder. R and Python are NOT removed.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"

# Safety check: only act inside a CalibraUV folder
if [ ! -f "$ROOT/app.py" ] || [ ! -f "$ROOT/calibrauv/methods.json" ]; then
  echo "This does not look like a CalibraUV folder: $ROOT"; exit 1
fi

echo "== CalibraUV: uninstall =="
echo "Folder: $ROOT"
read -r -p "Remove the virtual environment, caches and settings? [y/N] " ans
case "$ans" in [yYsS]*) ;; *) echo "Cancelled."; exit 0;; esac

rm -rf "$ROOT/.venv" "$ROOT/.pytest_cache" "$ROOT/user_settings.json"
find "$ROOT" -type d -name "__pycache__" -prune -exec rm -rf {} +
echo "Virtual environment, caches and settings removed."

if [ -f "$HOME/.streamlit/credentials.toml" ]; then
  read -r -p "Also remove Streamlit's settings file (~/.streamlit/credentials.toml)? Other Streamlit apps use it too. [y/N] " ans
  case "$ans" in [yYsS]*) rm -f "$HOME/.streamlit/credentials.toml"; echo "Removed.";; esac
fi

read -r -p "Delete the whole application folder (including your own data files in it)? [y/N] " ans
case "$ans" in
  [yYsS]*) cd /; rm -rf "$ROOT"; echo "Application folder deleted.";;
  *) echo "Folder kept. Reinstall at any time with ./scripts/install_linux.sh";;
esac
echo "R and Python were not removed (other programs may use them). To remove them: sudo apt remove r-base python3-venv"
