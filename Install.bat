@echo off
setlocal enabledelayedexpansion

cd /d "C:\Users\AnonymousBR\Desktop\Projetos Python\Tradutor 2.0"

echo ===================================================
echo             Instalador de Dependencias
echo             Translator By: LeNinjaMK
echo ===================================================
echo.

:: 1. Verificar se o Python ja esta instalado no sistema
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Python nao foi encontrado no seu sistema.
    echo [*] Iniciando o download automatico do Python 3.10.11 para Windows...
    
    :: URL oficial do instalador silencioso (executable installer) do Python 3.10.11 x64
    set "PYTHON_URL=https://www.python.org/ftp/python/3.10.11/python-3.10.11-amd64.exe"
    set "INSTALLER_NAME=python_installer.exe"
    
    :: Baixa usando PowerShell nativo do Windows
    powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object System.Net.WebClient).DownloadFile('!PYTHON_URL!', '!INSTALLER_NAME!')"
    
    if not exist "!INSTALLER_NAME!" (
        echo [X] Falha no download do instalador do Python. Verifique sua conexao de internet.
        pause
        exit /b
    )
    
    echo [*] Instalando Python silenciosamente. Por favor, aguarde...
    :: Executa instalacao silenciosa adicionando ao PATH para todos os usuarios
    start /wait "" "!INSTALLER_NAME!" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
    
    :: Limpa o instalador baixado
    del "!INSTALLER_NAME!"
    
    :: Recarrega a variavel PATH na sessao do CMD atual para reconhecer o Python instalado
    for /f "tokens=2*" %%A in ('reg query "HKLM\System\CurrentControlSet\Control\Session Manager\Environment" /v Path 2^>nul') do set "Path=%%B"
    for /f "tokens=2*" %%A in ('reg query "HKCU\Environment" /v Path 2^>nul') do set "Path=!Path!;%%B"
    
    :: Segunda checagem apos a instalacao
    python --version >nul 2>&1
    if !errorlevel! neq 0 (
        echo [X] A instalacao automatica do Python falhou ou requer reinicializacao do computador.
        echo Se o erro persistir, instale o Python manualmente em: https://www.python.org/
        pause
        exit /b
    )
    echo [✔️] Python instalado com sucesso!
) else (
    echo [✔️] Python ja esta instalado no sistema.
)
echo.

:: 2. Criar ambiente virtual se nao existir
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

:: 3. Instalar dependencias de forma visivel
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
