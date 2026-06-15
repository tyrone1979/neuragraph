# Inject api_key from meta/llms/.secrets/*.json, push to Gitee, restore redacted files locally.
# Usage: .\scripts\push_gitee.ps1 [-Branch 2.0]

param(
    [string]$Branch = "2.0"
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

$secretsDir = "meta/llms/.secrets"
if (-not (Test-Path $secretsDir)) {
    throw "Missing ${secretsDir}."
}

$backups = @{}
Get-ChildItem $secretsDir -Filter "*.json" | ForEach-Object {
    $target = "meta/llms/$($_.Name)"
    if (-not (Test-Path $target)) { return }
    & "$PSScriptRoot\_sanitize_deepseek.ps1" -TargetPath $target
    $backups[$target] = Get-Content $target -Raw -Encoding UTF8
    $secretCfg = Get-Content $_.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
    $cfg = $backups[$target] | ConvertFrom-Json
    $cfg.api_key = [string]$secretCfg.api_key
    ($cfg | ConvertTo-Json -Depth 10) + "`n" | Set-Content $target -Encoding UTF8 -NoNewline
}

if ($backups.Count -eq 0) {
    throw "No matching meta/llms/*.json files for secrets in ${secretsDir}."
}

git add @($backups.Keys)
$committed = $false
git diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
    git commit -m "chore(gitee): sync LLM configs with api_key"
    $committed = $true
} else {
    Write-Host "LLM configs unchanged; pushing current HEAD" -ForegroundColor Yellow
}

git push origin "HEAD:${Branch}"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "Pushed to origin:${Branch}" -ForegroundColor Green

if ($committed) {
    git reset --mixed HEAD~1 | Out-Null
}

foreach ($entry in $backups.GetEnumerator()) {
    Set-Content $entry.Key -Value $entry.Value -Encoding UTF8 -NoNewline
}
Write-Host "Restored local redacted LLM configs (safe for GitHub pushes)." -ForegroundColor Green
