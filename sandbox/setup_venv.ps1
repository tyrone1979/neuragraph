# Create / refresh a named plugin sandbox venv (Windows).
# Usage: .\sandbox\setup_venv.ps1 -Name flair
#        .\sandbox\setup_venv.ps1 -Name custom
# Linux / macOS: ./sandbox/setup_venv.sh flair
param(
    [Parameter(Mandatory = $false)]
    [string]$Name = "flair"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$manifestPath = Join-Path $root "meta\plugins_sandbox.json"
if (-not (Test-Path $manifestPath)) {
    Write-Host "[sandbox] manifest not found: $manifestPath" -ForegroundColor Red
    exit 1
}
$manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
$cfg = $manifest.sandboxes.$Name
if (-not $cfg) {
    Write-Host "[sandbox] Unknown sandbox '$Name' in meta/plugins_sandbox.json" -ForegroundColor Red
    exit 1
}

$sandboxDir = Join-Path $root "sandbox\$Name"
$venvDir = Join-Path $root ($cfg.venv -replace '/', '\')
$reqFile = Join-Path $sandboxDir "requirements.txt"
if (-not (Test-Path $reqFile)) {
    Write-Host "[sandbox] Missing $reqFile" -ForegroundColor Red
    exit 1
}

$sandboxPy = Join-Path $venvDir "Scripts\python.exe"

# Migrate legacy sandbox/venv -> sandbox/flair/venv
if ($Name -eq "flair") {
    $legacyVenv = Join-Path $root "sandbox\venv"
    if ((Test-Path $legacyVenv) -and -not (Test-Path $venvDir)) {
        Write-Host "[sandbox:flair] Moving legacy sandbox\venv -> sandbox\flair\venv ..."
        Move-Item $legacyVenv $venvDir
    }
}

if (-not (Test-Path $sandboxPy)) {
    Write-Host "[sandbox:$Name] Creating venv at $venvDir ..."
    py -3.11 -m venv $venvDir 2>$null
    if (-not (Test-Path $sandboxPy)) {
        & "$root\venv\Scripts\python.exe" -m venv $venvDir
    }
}

Write-Host "[sandbox:$Name] pip install ..."
& $sandboxPy -m pip install -U pip
& $sandboxPy -m pip install -r $reqFile

if ($Name -eq "flair") {
    Write-Host "[sandbox:flair] Installing torch CPU ..."
    & $sandboxPy -m pip install "torch==2.6.0+cpu" --index-url https://download.pytorch.org/whl/cpu
}

Write-Host "[sandbox:$Name] Verify imports ..."
if ($Name -eq "flair") {
    & $sandboxPy -c "import torch; import flair; print('torch', torch.__version__)"
} else {
    & $sandboxPy -c "print('venv ok')"
}

Write-Host "[sandbox:$Name] Done. Port $($cfg.port), entry $($cfg.entry)" -ForegroundColor Green
