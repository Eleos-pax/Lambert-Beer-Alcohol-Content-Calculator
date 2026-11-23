#!/usr/bin/env bash
# Updates CalibraUV to the latest version of the GitHub repository and its dependencies.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
REPO="https://github.com/Eleos-pax/Lambert-Beer-Content-Calculator"

echo "== CalibraUV: update =="
if [ -d .git ] && command -v git >/dev/null 2>&1; then
  echo "Git installation detected: downloading changes..."
  git pull --ff-only
else
  echo "ZIP installation detected: downloading the latest version..."
  for tool in curl unzip; do
    command -v "$tool" >/dev/null 2>&1 || { echo "Missing '$tool'. Install it with: sudo apt install $tool"; exit 1; }
  done
  TMP="$(mktemp -d)"
  trap 'rm -rf "$TMP"' EXIT
  curl -fsSL "$REPO/archive/refs/heads/main.zip" -o "$TMP/calibrauv.zip"
  unzip -q "$TMP/calibrauv.zip" -d "$TMP"
  SRC="$(find "$TMP" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
  # Copy the new files over the old ones (keeps .venv and your settings)
  cp -a "$SRC"/. "$ROOT"/
  chmod +x "$ROOT"/scripts/*.sh
fi

if [ -x .venv/bin/python ]; then
  echo "Updating Python dependencies..."
  .venv/bin/python -m pip install --upgrade -r requirements.txt
else
  echo "No virtual environment found: running the installer..."
  ./scripts/install_linux.sh
fi
echo
echo "Done. Start the app with:  ./scripts/run_linux.sh"
