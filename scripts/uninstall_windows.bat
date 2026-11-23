@echo off
REM Uninstalls CalibraUV: removes its virtual environment, caches and settings,
REM and optionally the whole application folder. R and Python are NOT removed.
setlocal
cd /d "%~dp0\.."
set "ROOT=%CD%"

REM Safety check: only act inside a CalibraUV folder
if not exist "%ROOT%\app.py" goto notapp
if not exist "%ROOT%\calibrauv\methods.json" goto notapp

echo == CalibraUV: uninstall ==
echo Folder: %ROOT%
choice /C YN /M "Remove the virtual environment, caches and settings"
if errorlevel 2 ( echo Cancelled. & pause & exit /b 0 )

if exist "%ROOT%\.venv" rmdir /s /q "%ROOT%\.venv"
if exist "%ROOT%\.pytest_cache" rmdir /s /q "%ROOT%\.pytest_cache"
if exist "%ROOT%\user_settings.json" del /q "%ROOT%\user_settings.json"
for /d /r "%ROOT%" %%d in (__pycache__) do if exist "%%d" rmdir /s /q "%%d"
echo Virtual environment, caches and settings removed.

if exist "%USERPROFILE%\.streamlit\credentials.toml" (
  choice /C YN /M "Also remove Streamlit settings file (other Streamlit apps use it too)"
  if not errorlevel 2 del /q "%USERPROFILE%\.streamlit\credentials.toml"
)

choice /C YN /M "Delete the whole application folder (including your own data files in it)"
if errorlevel 2 (
  echo Folder kept. Reinstall at any time with scripts\install_windows.bat
  goto end
)
echo R and Python were not removed. Uninstall them from Windows Settings ^> Apps if you no longer need them.
echo The folder will be deleted when this window closes.
pause
REM A batch file cannot delete the folder it runs from: a small helper in %TEMP% does it
set "CLEAN=%TEMP%\calibrauv_cleanup.bat"
> "%CLEAN%" echo @echo off
>>"%CLEAN%" echo timeout /t 2 /nobreak ^>nul
>>"%CLEAN%" echo rmdir /s /q "%ROOT%"
>>"%CLEAN%" echo del "%%~f0"
cd /d "%TEMP%"
start "" /min "%CLEAN%"
exit /b 0

:end
echo R and Python were not removed. Uninstall them from Windows Settings ^> Apps if you no longer need them.
pause
exit /b 0

:notapp
echo This does not look like a CalibraUV folder: %ROOT%
pause
exit /b 1
