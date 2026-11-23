@echo off
REM Updates CalibraUV to the latest version of the GitHub repository and its dependencies.
setlocal
cd /d "%~dp0\.."
set "ROOT=%CD%"
echo == CalibraUV: update ==

set "USEGIT=0"
if exist ".git" (where git >nul 2>nul && set "USEGIT=1")
if "%USEGIT%"=="1" (
  echo Git installation detected: downloading changes...
  git pull --ff-only
  if errorlevel 1 ( echo Error updating with git & pause & exit /b 1 )
) else (
  echo ZIP installation detected: downloading the latest version...
  powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\update_from_zip.ps1" -Root "%ROOT%"
  if errorlevel 1 ( echo Error downloading the update & pause & exit /b 1 )
)

if exist ".venv\Scripts\python.exe" (
  echo Updating Python dependencies...
  .venv\Scripts\python.exe -m pip install --upgrade -r requirements.txt
) else (
  echo No virtual environment found: running the installer...
  call scripts\install_windows.bat
)
echo.
echo Done. Start the app with scripts\run_windows.bat
pause
