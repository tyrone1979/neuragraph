# Stop processes listening on NeuraGraph ports (5001 Flask, 5002+ sandboxes).
$ports = 5001, 5002
$procIds = @(Get-NetTCPConnection -LocalPort $ports -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique |
    Where-Object { $_ -gt 0 })
foreach ($procId in $procIds) {
    Write-Host "  Stopping PID $procId"
    Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
}
