@echo off
cd /d "%~dp0"
call venv\Scripts\activate.bat
set PYTHONPATH=%CD%
set PLUGIN_SANDBOX=1

echo Checking flair sandbox (port 5002)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r=Invoke-WebRequest -Uri 'http://127.0.0.1:5002/health' -UseBasicParsing -TimeoutSec 2; if($r.StatusCode -eq 200){ exit 0 } else { exit 1 } } catch { exit 1 }"
if errorlevel 1 (
  if exist "sandbox\flair\venv\Scripts\python.exe" (
    echo [sandbox] Starting flair sandbox...
    start "" /min powershell -NoProfile -ExecutionPolicy Bypass -File "%CD%\scripts\start_plugin_sandbox.ps1" -Name flair
    timeout /t 2 /nobreak >nul
  ) else (
    echo [sandbox] flair venv not found. Run: .\sandbox\setup_venv.ps1 -Name flair
  )
) else (
  echo [sandbox] flair already running.
)

set ARGS=%*
if "%~1"=="" set ARGS=--llm deepseek

echo Starting NeuraGraph terminal chat...
echo python chat.py %ARGS%
python chat.py %ARGS%
pause
