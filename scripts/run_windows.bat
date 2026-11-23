@echo off
REM Starts CalibraUV in the browser (http://localhost:8501)
cd /d "%~dp0\.."
if not exist ".venv\Scripts\streamlit.exe" (
  echo Run scripts\install_windows.bat first
  pause
  exit /b 1
)
REM Skip Streamlit's one-time e-mail prompt (no data is sent)
if not exist "%USERPROFILE%\.streamlit\credentials.toml" (
  if not exist "%USERPROFILE%\.streamlit" mkdir "%USERPROFILE%\.streamlit"
  (echo [general]& echo email = "") > "%USERPROFILE%\.streamlit\credentials.toml"
)
.venv\Scripts\streamlit.exe run app.py
