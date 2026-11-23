@echo off
REM Starts CalibraUV in the browser (http://localhost:8501)
cd /d "%~dp0\.."
if not exist ".venv\Scripts\streamlit.exe" (
  echo Run scripts\install_windows.bat first
  pause
  exit /b 1
)
.venv\Scripts\streamlit.exe run app.py
