# Inject api_key from meta/llms/.secrets/deepseek.json, push to Gitee, restore redacted file locally.
# Usage: .\scripts\push_gitee.ps1 [-Branch 2.0]

param(
    [string]$Branch = "2.0"
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

$deepseek = "meta/llms/deepseek.json"
$secrets = "meta/llms/.secrets/deepseek.json"

if (-not (Test-Path $secrets)) {
    throw "Missing ${secrets}. Copy your keyed deepseek.json there (gitignored)."
}

& "$PSScriptRoot\_sanitize_deepseek.ps1" -TargetPath $deepseek
$sanitized = Get-Content $deepseek -Raw -Encoding UTF8
$secretCfg = Get-Content $secrets -Raw -Encoding UTF8 | ConvertFrom-Json
$cfg = $sanitized | ConvertFrom-Json
$cfg.api_key = [string]$secretCfg.api_key
($cfg | ConvertTo-Json -Depth 10) + "`n" | Set-Content $deepseek -Encoding UTF8 -NoNewline

git add $deepseek
$committed = $false
git diff --cached --quiet -- $deepseek
if ($LASTEXITCODE -ne 0) {
    git commit -m "chore(gitee): sync deepseek llm config"
    $committed = $true
} else {
    Write-Host "deepseek.json unchanged; pushing current HEAD" -ForegroundColor Yellow
}

git push origin "HEAD:${Branch}"
Write-Host "Pushed to origin:${Branch}" -ForegroundColor Green

if ($committed) {
    git reset --mixed HEAD~1 | Out-Null
}

Set-Content $deepseek -Value $sanitized -Encoding UTF8 -NoNewline
Write-Host "Restored local redacted deepseek.json (safe for GitHub pushes)." -ForegroundColor Green
