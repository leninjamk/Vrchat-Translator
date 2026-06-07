@echo off
cd /d "%~dp0"

echo ===================================================
echo             Instalador de Dependencias
echo             Translator By: LeNinjaMK
echo ===================================================
echo.

:: 1. Procurar uma instalação estável do Python (3.10 ou 3.11)
if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
    set "PY_PATH=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    goto python_found
)
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set "PY_PATH=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    goto python_found
)
if exist "%ProgramFiles%\Python310\python.exe" (
    set "PY_PATH=%ProgramFiles%\Python310\python.exe"
    goto python_found
)
if exist "%ProgramFiles%\Python311\python.exe" (
    set "PY_PATH=%ProgramFiles%\Python311\python.exe"
    goto python_found
)
if exist "%ProgramFiles(x86)%\Python310\python.exe" (
    set "PY_PATH=%ProgramFiles(x86)%\Python310\python.exe"
    goto python_found
)
if exist "%ProgramFiles(x86)%\Python311\python.exe" (
    set "PY_PATH=%ProgramFiles(x86)%\Python311\python.exe"
    goto python_found
)
if exist "C:\Python310\python.exe" (
    set "PY_PATH=C:\Python310\python.exe"
    goto python_found
)
if exist "C:\Python311\python.exe" (
    set "PY_PATH=C:\Python311\python.exe"
    goto python_found
)

:: Se não achou nos caminhos tradicionais, tenta usar o comando global se for 3.10 ou 3.11
python --version >nul 2>&1
if errorlevel 1 goto download_python

for /f "tokens=2" %%v in ('python --version 2^>&1') do set "PY_VER=%%v"
echo %PY_VER% | findstr /r "^3\.10\." >nul
if not errorlevel 1 (
    set "PY_PATH=python"
    goto python_found
)
echo %PY_VER% | findstr /r "^3\.11\." >nul
if not errorlevel 1 (
    set "PY_PATH=python"
    goto python_found
)

:download_python
echo [!] Python estavel (3.10/3.11) nao foi encontrado no sistema.
echo [*] Iniciando o download do Python 3.10.11...
powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object System.Net.WebClient).DownloadFile('https://www.python.org/ftp/python/3.10.11/python-3.10.11-amd64.exe', 'python_installer.exe')"

if exist "python_installer.exe" goto start_install
echo [X] Falha no download do instalador do Python. Verifique sua conexao de internet.
goto end_error

:start_install
echo [*] Abrindo instalador do Python de forma VISIVEL...
echo [IMPORTANTE] Marque a opcao "Add Python to PATH" antes de clicar em instalar!
start /wait "" "python_installer.exe"
del "python_installer.exe"

:: Atualiza PATH do prompt temporariamente
for /f "tokens=2*" %%A in ('reg query "HKLM\System\CurrentControlSet\Control\Session Manager\Environment" /v Path 2^>nul') do set "Path=%%B"
for /f "tokens=2*" %%A in ('reg query "HKCU\Environment" /v Path 2^>nul') do set "Path=!Path!;%%B"

if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
    set "PY_PATH=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    goto python_found
)
python --version >nul 2>&1
if not errorlevel 1 (
    set "PY_PATH=python"
    goto python_found
)
echo [X] O Python nao foi detectado apos a instalacao.
goto end_error

:python_found
echo [✔️] Python selecionado para criacao do ambiente: %PY_PATH%
echo.

:: 2. Limpar a .venv antiga para evitar conflitos de versão
if exist ".venv" (
    echo [*] Limpando pasta .venv existente para evitar conflitos de versao...
    rmdir /s /q ".venv"
)

echo [*] Criando novo ambiente virtual (.venv) usando a versao estavel...
"%PY_PATH%" -m venv .venv
if errorlevel 1 (
    echo [X] Erro ao criar o ambiente virtual.
    goto end_error
)
echo [✔️] Ambiente virtual criado com sucesso!
echo.

:: 3. Instalar as dependências usando o isolamento "python.exe -m pip"
echo [*] Instalando dependencias (requirements.txt)...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if not errorlevel 1 goto install_ok

echo [X] Falha na instalacao de dependencias.
goto end_error

:install_ok
echo.
echo ===================================================
echo [✔️] INSTALACAO CONCLUIDA COM SUCESSO!
echo Voce ja pode fechar esta janela e rodar o "Run.bat"
echo ===================================================
echo.
pause
exit /b

:end_error
echo.
echo [X] Falha ao concluir a instalacao. Verifique as mensagens acima.
echo.
pause
exit /b
