# Push to GitHub with redacted LLM configs (no api_key in tracked files).
# Usage: .\scripts\push_github.ps1 [-Branch 2.0]

param(
    [string]$Branch = "2.0"
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

$secretsDir = "meta/llms/.secrets"
$changed = @()
Get-ChildItem $secretsDir -Filter "*.json" | ForEach-Object {
    $target = "meta/llms/$($_.Name)"
    if (-not (Test-Path $target)) { return }
    & "$PSScriptRoot\_sanitize_deepseek.ps1" -TargetPath $target
    $changed += $target
}

if ($changed.Count -gt 0) {
    git add @changed
    git diff --cached --quiet
    if ($LASTEXITCODE -ne 0) {
        git commit -m "chore: redact LLM api_key fields for GitHub"
    }
}

git push github "HEAD:${Branch}"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "Pushed sanitized branch to github:${Branch}" -ForegroundColor Green
