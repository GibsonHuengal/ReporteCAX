@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ============================================================
echo    Ciudad Inteligente - Cajamarca
echo ============================================================

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] No se encontro Python.
  echo         Instala Python 3.10 o superior desde https://www.python.org/downloads/
  echo         y marca la casilla "Add python.exe to PATH".
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [1/4] Creando entorno virtual ^(.venv^)...
  python -m venv .venv
  if errorlevel 1 (
    echo [ERROR] No se pudo crear el entorno virtual.
    pause
    exit /b 1
  )
) else (
  echo [1/4] Entorno virtual ya existe.
)

echo [2/4] Instalando dependencias...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 (
  echo [ERROR] Fallo la instalacion de dependencias.
  echo         Verifica tu conexion a internet.
  pause
  exit /b 1
)

if not exist "data\users.json" (
  echo [3/4] Creando usuarios de prueba...
  ".venv\Scripts\python.exe" seed_users.py
) else (
  echo [3/4] Usuarios de prueba ya existen.
)

echo [4/4] Iniciando servidor en http://127.0.0.1:5000
echo        Presiona Ctrl+C para detener.
echo.
".venv\Scripts\python.exe" app.py

pause
