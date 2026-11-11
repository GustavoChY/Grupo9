@echo off
chcp 65001 >nul
title Definitively Bolivia - Servidor
cd /d "%~dp0"
if not exist venv\Scripts\python.exe ( echo Primero ejecute instalar.bat & pause & exit /b 1 )
echo Iniciando el sistema... abra http://127.0.0.1:8000 en su navegador.
echo (Para detenerlo cierre esta ventana o pulse Ctrl+C)
start "" http://127.0.0.1:8000
venv\Scripts\python manage.py runserver 127.0.0.1:8000 --noreload
pause
