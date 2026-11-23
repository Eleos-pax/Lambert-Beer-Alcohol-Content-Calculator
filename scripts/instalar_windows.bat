@echo off
REM Instalador de CalibraUV para Windows 10/11
chcp 65001 >nul
cd /d "%~dp0\.."
echo == CalibraUV: instalacion en Windows ==

where py >nul 2>nul
if %errorlevel%==0 (set PY=py -3) else (set PY=python)
%PY% --version >nul 2>nul
if errorlevel 1 (
  echo Falta Python 3.10 o superior. Instalelo con:
  echo    winget install Python.Python.3.12
  echo o desde https://www.python.org/downloads/ marcando "Add python.exe to PATH".
  pause
  exit /b 1
)

where Rscript >nul 2>nul
if errorlevel 1 (
  if not exist "%ProgramFiles%\R" (
    echo AVISO: R no esta instalado. La app funcionara con el motor Python.
    echo        Para usar el motor de R recomendado:  winget install RProject.R
  )
)

%PY% -m venv .venv
if errorlevel 1 ( echo Error creando el entorno virtual & pause & exit /b 1 )
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 ( echo Error instalando dependencias & pause & exit /b 1 )

echo.
echo Listo. Para iniciar la aplicacion haga doble clic en scripts\ejecutar_windows.bat
pause
