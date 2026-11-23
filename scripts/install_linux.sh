#!/usr/bin/env bash
# CalibraUV installer for Ubuntu / Linux Mint (and other Debian derivatives)
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== CalibraUV: Linux installation =="

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is missing. Install it with:  sudo apt install python3 python3-venv python3-pip"
  exit 1
fi

if ! python3 -c "import venv, ensurepip" >/dev/null 2>&1; then
  echo "The venv module is missing. Install it with:  sudo apt install python3-venv"
  exit 1
fi

if ! command -v Rscript >/dev/null 2>&1; then
  echo "NOTE: R is not installed. The app will run with the Python engine."
  echo "      To use the R engine (recommended):  sudo apt install r-base"
fi

python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt

echo
echo "Done. To start the application run:  ./scripts/run_linux.sh"
