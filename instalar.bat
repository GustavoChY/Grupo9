@echo off
chcp 65001 >nul
title Instalador - Definitively Bolivia
cd /d "%~dp0"
echo ===============================================
echo   Definitively Bolivia - Instalacion del sistema
echo ===============================================
echo.
set PY=
py -3 --version >nul 2>&1 && set PY=py -3
if "%PY%"=="" ( python --version >nul 2>&1 && set PY=python )
if "%PY%"=="" (
  echo [ERROR] No se encontro Python. Instale Python 3.10 o superior desde https://www.python.org/downloads/
  echo         IMPORTANTE: marque la casilla "Add python.exe to PATH" durante la instalacion.
  pause & exit /b 1
)
echo [1/4] Creando entorno virtual...
if not exist venv\Scripts\python.exe %PY% -m venv venv
if errorlevel 1 ( echo [ERROR] No se pudo crear el entorno virtual. & pause & exit /b 1 )
echo [2/4] Instalando Django y psycopg (necesita internet)...
venv\Scripts\python -m pip install --upgrade pip >nul
venv\Scripts\python -m pip install -r requirements.txt
if errorlevel 1 ( echo [ERROR] Fallo la instalacion de paquetes. Revise su conexion a internet. & pause & exit /b 1 )
echo [3/4] Configuracion de PostgreSQL...
if not exist .env ( venv\Scripts\python configurar.py ) else ( echo Ya existe el archivo .env - se conserva. Borrelo si quiere reconfigurar. )
echo [4/4] Creando la base de datos y cargando los datos de ejemplo...
venv\Scripts\python manage.py instalar_bd
if errorlevel 1 ( echo. & echo [ERROR] No se pudo instalar la base de datos. Revise el mensaje de arriba. & pause & exit /b 1 )
echo.
echo ===============================================
echo   LISTO. Ahora ejecute  iniciar.bat
echo ===============================================
pause
