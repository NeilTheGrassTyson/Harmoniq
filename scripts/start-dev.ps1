# scripts/start-dev.ps1
$backendPath = "$PSScriptRoot\..\backend"

$venvUvicorn = if (Test-Path "$backendPath\.venv\Scripts\uvicorn.exe") {
    "$backendPath\.venv\Scripts\uvicorn.exe"
} elseif (Test-Path "$backendPath\venv\Scripts\uvicorn.exe") {
    "$backendPath\venv\Scripts\uvicorn.exe"
} else {
    Write-Error "Couldn't find uvicorn.exe in backend\.venv or backend\venv -- check your venv folder name."
    exit 1
}

$backendProc  = Start-Process powershell -ArgumentList "-NoExit -Command cd '$backendPath'; & '$venvUvicorn' app.main:app --reload" -PassThru
$frontendProc = Start-Process powershell -ArgumentList "-NoExit -Command cd '$PSScriptRoot\..\frontend'; npm run dev" -PassThru

@{ BackendPid = $backendProc.Id; FrontendPid = $frontendProc.Id } |
    ConvertTo-Json |
    Set-Content "$env:TEMP\harmoniq-dev-pids.json" -Encoding utf8

Write-Host "Frontend: http://localhost:3000"
Write-Host "Backend:  http://localhost:8000"
Write-Host ""
Write-Host "Run .\scripts\stop-dev.ps1 to shut down."
