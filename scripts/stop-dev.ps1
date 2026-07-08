# scripts/stop-dev.ps1
$pidFile = "$env:TEMP\harmoniq-dev-pids.json"

if (-not (Test-Path $pidFile)) {
    Write-Host "No running dev session found (PID file missing)."
    exit 0
}

$pids = Get-Content $pidFile -Raw | ConvertFrom-Json
Remove-Item $pidFile -Force

foreach ($id in @($pids.BackendPid, $pids.FrontendPid)) {
    if ($id) {
        # /T kills the whole process tree (the PowerShell window + uvicorn/node children)
        taskkill /F /PID $id /T 2>$null | Out-Null
    }
}

Write-Host "Dev environment stopped."
