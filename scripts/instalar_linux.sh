#!/usr/bin/env bash
# Instalador de CalibraUV para Ubuntu / Linux Mint (y derivadas de Debian)
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== CalibraUV: instalación en Linux =="

if ! command -v python3 >/dev/null 2>&1; then
  echo "Falta Python 3. Instálelo con:  sudo apt install python3 python3-venv python3-pip"
  exit 1
fi

if ! python3 -c "import venv, ensurepip" >/dev/null 2>&1; then
  echo "Falta el módulo venv. Instálelo con:  sudo apt install python3-venv"
  exit 1
fi

if ! command -v Rscript >/dev/null 2>&1; then
  echo "AVISO: R no está instalado. La app funcionará con el motor Python."
  echo "       Para usar el motor de R (recomendado):  sudo apt install r-base"
fi

python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt

echo
echo "Listo. Para iniciar la aplicación ejecute:  ./scripts/ejecutar_linux.sh"
