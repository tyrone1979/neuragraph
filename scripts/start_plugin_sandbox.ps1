# Start one named sandbox (see meta/plugins_sandbox.json).
param(
    [Parameter(Mandatory = $false)]
    [string]$Name = "flair"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$manifest = Get-Content "$root\meta\plugins_sandbox.json" -Raw | ConvertFrom-Json
$cfg = $manifest.sandboxes.$Name
if (-not $cfg) {
    Write-Host "Unknown sandbox: $Name" -ForegroundColor Red
    exit 1
}

$venvRoot = Join-Path $root ($cfg.venv -replace '/', '\')
$venvPy = Join-Path $venvRoot "Scripts\python.exe"
$entry = Join-Path $root ($cfg.entry -replace '/', '\')
if (-not (Test-Path $venvPy)) {
    Write-Host "Run: .\sandbox\setup_venv.ps1 -Name $Name" -ForegroundColor Red
    exit 1
}

$env:PYTHONPATH = $root
$env:SANDBOX_ID = $Name
$env:PLUGIN_SERVER_PORT = "$($cfg.port)"
Write-Host "Starting sandbox '$Name' on port $($cfg.port)..." -ForegroundColor Green
& $venvPy $entry
