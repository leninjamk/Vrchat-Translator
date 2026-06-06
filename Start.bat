@echo off
setlocal

cd /d "%~dp0"

echo ==========================
echo   VRCHAT TRANSLATOR
echo ==========================

echo Usando Python da venv direto...

"%~dp0.venv\Scripts\python.exe" "ui\app.py"

echo.
echo Programa finalizado.
pause