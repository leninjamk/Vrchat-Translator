@echo off
setlocal enabledelayedexpansion

cd /d "C:\Users\AnonymousBR\Desktop\Projetos Python\Tradutor 2.0"

echo ===================================================
echo             Instalador de Dependencias
echo             Translator By: LeNinjaMK
echo ===================================================
echo.

:: 1. Verificar se o Python está no PATH
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [X] Erro: Python nao encontrado no sistema!
    echo Certifique-se de instalar o Python 3.10 ou superior e marcar a opcao "Add Python to PATH".
    echo.
    pause
    exit /b
)

:: 2. Criar ambiente virtual se não existir
if not exist ".venv" (
    echo [*] Criando ambiente virtual (.venv)...
    python -m venv .venv
    if !errorlevel! neq 0 (
        echo [X] Erro ao criar o ambiente virtual.
        pause
        exit /b
    )
    echo [✔️] Ambiente virtual criado com sucesso!
) else (
    echo [✔️] Ambiente virtual ja existente.
)
echo.

:: 3. Instalar dependências de forma visível
echo [*] Instalando dependencias (requirements.txt)...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\pip.exe" install -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo [X] Ocorreu um erro durante a instalacao dos requisitos.
    echo Verifique os logs acima e sua conexao com a internet.
    echo.
    pause
    exit /b
)

echo.
echo ===================================================
echo [✔️] INSTALACAO CONCLUIDA COM SUCESSO!
echo Agora voce ja pode fechar esta janela e rodar o "Run.bat"
echo ===================================================
echo.
pause
