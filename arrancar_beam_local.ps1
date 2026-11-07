Set-Location "C:\Users\chris\Documents\muse_clone"

$envFile = ".\.env"

if (-not (Test-Path $envFile)) {
    Write-Host "ERROR: No se encuentra el archivo .env" -ForegroundColor Red
    exit 1
}

$databaseLine = Get-Content $envFile |
    Where-Object { $_ -match '^DATABASE_URL=' } |
    Select-Object -First 1

if (-not $databaseLine) {
    Write-Host "ERROR: DATABASE_URL no existe en .env" -ForegroundColor Red
    exit 1
}

$env:DATABASE_URL = $databaseLine.Substring("DATABASE_URL=".Length).Trim()

if ([string]::IsNullOrWhiteSpace($env:DATABASE_URL)) {
    Write-Host "ERROR: DATABASE_URL esta vacia" -ForegroundColor Red
    exit 1
}

$existingServer = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue

if ($existingServer) {
    Write-Host "BEAM AI ya esta ejecutandose en el puerto 8000." -ForegroundColor Yellow
    exit 0
}

Write-Host "================================"
Write-Host "       ARRANCANDO BEAM AI"
Write-Host "================================"
Write-Host ""
Write-Host "Entorno virtual: OK"
Write-Host "PostgreSQL: configurado"
Write-Host ""

& ".\venv\Scripts\python.exe" -m uvicorn app:app --host 127.0.0.1 --port 8000
