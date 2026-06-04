@echo off
cd /d "%~dp0"
call venv\Scripts\activate.bat
set PYTHONPATH=%CD%
set PLUGIN_SANDBOX=1

echo Stopping old listeners on ports 5001 / 5002...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\kill_ports.ps1"
timeout /t 2 /nobreak >nul

echo Starting plugin sandboxes...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0sandbox\launch_all.ps1"
timeout /t 4 /nobreak >nul

echo Starting Flask http://localhost:5001
"%~dp0venv\Scripts\python.exe" -m ui.app
pause
