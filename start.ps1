# NeuraGraph 启动脚本 (PowerShell)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  NeuraGraph - AI Workflow Platform" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 获取脚本所在目录
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

Write-Host "[1/3] 激活虚拟环境..." -ForegroundColor Yellow
& "$scriptDir\venv\Scripts\Activate.ps1"

Write-Host "`n[2/3] 设置环境变量..." -ForegroundColor Yellow
$env:PYTHONPATH = $scriptDir

Write-Host "`n[3/3] 启动 Flask 应用..." -ForegroundColor Yellow
Write-Host ""
Write-Host "访问地址: http://localhost:5001" -ForegroundColor Green
Write-Host "按 Ctrl+C 停止服务" -ForegroundColor Yellow
Write-Host ""

# 启动应用
& "$scriptDir\venv\Scripts\python.exe" -m ui.app
