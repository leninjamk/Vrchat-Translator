@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

echo ===================================================
echo             Translator By: LeNinjaMK
echo ===================================================
echo.

:: 1. Verificar se o Python está instalado
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [X] Python nao foi encontrado no sistema.
    echo Por favor, instale o Python 3.10 ou superior e marque a opcao "Add Python to PATH" durante a instalacao.
    echo.
    pause
    exit /b
)

:: 2. Criar ambiente virtual (.venv) se nao existir
if not exist ".venv" (
    echo [*] Criando ambiente virtual (.venv)...
    python -m venv .venv
    if !errorlevel! neq 0 (
        echo [X] Falha ao criar o ambiente virtual.
        pause
        exit /b
    )
)

:: 3. Instalar dependencias automaticamente
echo [*] Verificando e instalando dependencias (requirements.txt)...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\pip.exe" install -r requirements.txt
if %errorlevel% neq 0 (
    echo [X] Erro ao instalar os requisitos. Verifique sua conexao de internet.
    pause
    exit /b
)

:: 4. Iniciar o programa
echo [*] Iniciando o VRChat Translator...
echo.
".venv\Scripts\python.exe" "ui\app.py"

echo.
echo Programa finalizado.
pause