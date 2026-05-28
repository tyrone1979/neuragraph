# Start all enabled sandboxes in background (non-blocking).
$ErrorActionPreference = "SilentlyContinue"
$root = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = $root
$manifest = Get-Content "$root\meta\plugins_sandbox.json" -Raw | ConvertFrom-Json
foreach ($prop in $manifest.sandboxes.PSObject.Properties) {
    $id = $prop.Name
    $cfg = $prop.Value
    if ($cfg.enabled -eq $false) { continue }
    $venvRoot = Join-Path $root ($cfg.venv -replace '/', '\')
    $venvPy = Join-Path $venvRoot "Scripts\python.exe"
    $entry = Join-Path $root ($cfg.entry -replace '/', '\')
    if (-not (Test-Path $venvPy)) { continue }
    $env:PLUGIN_SERVER_PORT = "$($cfg.port)"
    $env:SANDBOX_ID = $id
    Start-Process -FilePath $venvPy -ArgumentList $entry -WorkingDirectory $root -WindowStyle Hidden
}
