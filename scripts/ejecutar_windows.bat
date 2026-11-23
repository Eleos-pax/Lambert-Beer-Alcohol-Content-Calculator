@echo off
REM Inicia CalibraUV en el navegador (http://localhost:8501)
cd /d "%~dp0\.."
if not exist ".venv\Scripts\streamlit.exe" (
  echo Primero ejecute scripts\instalar_windows.bat
  pause
  exit /b 1
)
.venv\Scripts\streamlit.exe run app.py
