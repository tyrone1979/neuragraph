# Push to GitHub with a redacted deepseek.json (no api_key).
# Usage: .\scripts\push_github.ps1 [-Branch 2.0]

param(
    [string]$Branch = "2.0"
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

$deepseek = "meta/llms/deepseek.json"
& "$PSScriptRoot\_sanitize_deepseek.ps1" -TargetPath $deepseek

git add $deepseek .gitignore
$status = git status --porcelain $deepseek
if ($status) {
    git commit -m "chore: keep deepseek.json without api_key for GitHub"
}

git push github "HEAD:${Branch}"
Write-Host "Pushed sanitized branch to github:${Branch}" -ForegroundColor Green
