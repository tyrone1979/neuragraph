# Start all enabled sandboxes from meta/plugins_sandbox.json (foreground helper).
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$env:PYTHONPATH = $root
& "$root\venv\Scripts\python.exe" "$root\scripts\start_sandboxes.py"
