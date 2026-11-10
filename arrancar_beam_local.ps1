Set-Location "C:\Users\chris\Documents\muse_clone"

$envFile = ".\.env"

if (-not (Test-Path $envFile)) {
    Write-Host "ERROR: No se encuentra el archivo .env" -ForegroundColor Red
    exit 1
}

$requiredVariables = @(
    "DATABASE_URL",
    "XAI_API_KEY",
    "OTEL_SERVICE_NAME",
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "OTEL_EXPORTER_OTLP_PROTOCOL",
    "OTEL_EXPORTER_OTLP_HEADERS"
)

foreach ($variableName in $requiredVariables) {
    $line = Get-Content $envFile |
        Where-Object { $_ -match "^$variableName=" } |
        Select-Object -First 1

    if (-not $line) {
        Write-Host "ERROR: $variableName no existe en .env" -ForegroundColor Red
        exit 1
    }

    $value = $line.Substring($variableName.Length + 1).Trim()

    if ([string]::IsNullOrWhiteSpace($value)) {
        Write-Host "ERROR: $variableName esta vacia" -ForegroundColor Red
        exit 1
    }

    Set-Item -Path "Env:$variableName" -Value $value
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

& ".\venv\Scripts\opentelemetry-instrument.exe" `
    ".\venv\Scripts\python.exe" `
    -m uvicorn app:app `
    --host 127.0.0.1 `
    --port 8000
