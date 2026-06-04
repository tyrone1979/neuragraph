# Backup RE baseline results — run after completion
$src = "D:\projects\neuragraph\result\c422b97c-be21-4b6a-968c-c4994229d702"
$dst = "D:\projects\neuragraph\result\c422b97c-be21-4b6a-968c-c4994229d702.BACKUP"

if (Test-Path $src) {
    if (Test-Path $dst) {
        Remove-Item -Recurse -Force $dst
    }
    Copy-Item -Recurse -Force $src $dst
    Write-Host "BACKUP OK: $src -> $dst"
} else {
    Write-Host "WARNING: source $src not found"
}

# Also copy summary JSON
$summary = "D:\projects\neuragraph\result\perf34_wf_cid_re_llm_linear_summary.json"
if (Test-Path $summary) {
    Copy-Item -Force $summary "D:\projects\neuragraph\result\perf34_wf_cid_re_llm_linear_summary.BACKUP.json"
    Write-Host "BACKUP OK: summary"
}
