@echo off
REM CalibraUV installer for Windows 10/11
cd /d "%~dp0\.."
echo == CalibraUV: Windows installation ==

where py >nul 2>nul
if %errorlevel%==0 (set PY=py -3) else (set PY=python)
%PY% --version >nul 2>nul
if errorlevel 1 (
  echo Python 3.10 or newer is missing. Install it with:
  echo    winget install Python.Python.3.12
  echo or from https://www.python.org/downloads/ ticking "Add python.exe to PATH".
  pause
  exit /b 1
)

where Rscript >nul 2>nul
if errorlevel 1 (
  if not exist "%ProgramFiles%\R" (
    echo NOTE: R is not installed. The app will run with the Python engine.
    echo       To use the recommended R engine:  winget install RProject.R
  )
)

%PY% -m venv .venv
if errorlevel 1 ( echo Error creating the virtual environment & pause & exit /b 1 )
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 ( echo Error installing dependencies & pause & exit /b 1 )

echo.
echo Done. To start the application double-click scripts\run_windows.bat
pause
