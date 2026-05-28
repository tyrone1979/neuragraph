# NeuraGraph 启动脚本 (PowerShell)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  NeuraGraph - AI Workflow Platform" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

Write-Host "[1/4] 激活主虚拟环境..." -ForegroundColor Yellow
& "$scriptDir\venv\Scripts\Activate.ps1"

Write-Host "`n[2/4] 设置环境变量..." -ForegroundColor Yellow
$env:PYTHONPATH = $scriptDir
$env:PLUGIN_SANDBOX = "1"

Write-Host "`n[3/5] 释放端口 5001 / 5002..." -ForegroundColor Yellow
& "$scriptDir\scripts\kill_ports.ps1"
Start-Sleep -Seconds 2

Write-Host "`n[4/5] 启动 Plugin Sandboxes (manifest)..." -ForegroundColor Yellow
$sandboxJobs = @()
$manifest = Get-Content "$scriptDir\meta\plugins_sandbox.json" -Raw | ConvertFrom-Json
foreach ($prop in $manifest.sandboxes.PSObject.Properties) {
    $id = $prop.Name
    $cfg = $prop.Value
    if ($cfg.enabled -eq $false) { continue }
    $venvRoot = Join-Path $scriptDir ($cfg.venv -replace '/', '\')
    $venvPy = Join-Path $venvRoot "Scripts\python.exe"
    $entry = Join-Path $scriptDir ($cfg.entry -replace '/', '\')
    if (-not (Test-Path $venvPy)) {
        Write-Host "  [skip] $id — venv missing. Run: .\sandbox\setup_venv.ps1 -Name $id" -ForegroundColor Yellow
        continue
    }
    $env:PLUGIN_SERVER_PORT = "$($cfg.port)"
    $env:SANDBOX_ID = $id
    $job = Start-Process -FilePath $venvPy `
        -ArgumentList $entry `
        -WorkingDirectory $scriptDir `
        -PassThru `
        -WindowStyle Hidden
    $sandboxJobs += $job
    Start-Sleep -Seconds 2
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:$($cfg.port)/health" -TimeoutSec 5 -UseBasicParsing
        if ($r.StatusCode -eq 200) {
            Write-Host "  [OK] sandbox '$id' -> :$($cfg.port)" -ForegroundColor Green
        }
    } catch {
        Write-Host "  [WARN] sandbox '$id' not responding on :$($cfg.port)" -ForegroundColor Yellow
    }
}

Write-Host "`n[5/5] 启动 Flask 应用 (port 5001)..." -ForegroundColor Yellow
Write-Host ""
Write-Host "主应用: http://localhost:5001" -ForegroundColor Green
Write-Host "Manifest: meta/plugins_sandbox.json" -ForegroundColor Green
Write-Host ""

try {
    & "$scriptDir\venv\Scripts\python.exe" -m ui.app
} finally {
    foreach ($job in $sandboxJobs) {
        if ($job -and -not $job.HasExited) {
            Stop-Process -Id $job.Id -Force -ErrorAction SilentlyContinue
        }
    }
}
