# ============================================================
#  Ciudad Inteligente - Cajamarca
#  Script de arranque para PowerShell.
#  Uso:  .\iniciar.ps1
#  Si Windows bloquea el script, ejecuta primero:
#     Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned -Force
# ============================================================
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "   Ciudad Inteligente - Cajamarca" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] No se encontro Python. Instala Python 3.10+ desde python.org" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "[1/4] Creando entorno virtual (.venv)..." -ForegroundColor Yellow
    python -m venv .venv
} else {
    Write-Host "[1/4] Entorno virtual ya existe." -ForegroundColor Green
}

Write-Host "[2/4] Instalando dependencias..." -ForegroundColor Yellow
& ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt

if (-not (Test-Path "data\users.json")) {
    Write-Host "[3/4] Creando usuarios de prueba..." -ForegroundColor Yellow
    & ".venv\Scripts\python.exe" seed_users.py
} else {
    Write-Host "[3/4] Usuarios de prueba ya existen." -ForegroundColor Green
}

Write-Host "[4/4] Iniciando servidor en http://127.0.0.1:5000 (Ctrl+C para detener)" -ForegroundColor Green
& ".venv\Scripts\python.exe" app.py
