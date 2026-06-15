param(
    [Parameter(Mandatory = $true)]
    [string]$TargetPath
)

$cfg = Get-Content $TargetPath -Raw -Encoding UTF8 | ConvertFrom-Json
$cfg.api_key = ""
($cfg | ConvertTo-Json -Depth 10) + "`n" | Set-Content $TargetPath -Encoding UTF8 -NoNewline
