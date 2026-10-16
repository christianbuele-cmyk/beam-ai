Set-Location "C:\Users\chris\Documents\muse_clone"

& ".\venv\Scripts\Activate.ps1"

Write-Host "================================"
Write-Host "       ARRANCANDO BEAM AI"
Write-Host "================================"
Write-Host ""

python -m uvicorn app:app --host 127.0.0.1 --port 8000
