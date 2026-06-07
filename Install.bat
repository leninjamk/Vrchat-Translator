@echo off
cd /d "%~dp0"

echo ===================================================
echo             Instalador de Dependencias
echo             Translator By: LeNinjaMK
echo ===================================================
echo.

:: 1. Procurar e priorizar uma instalação estável do Python (3.10 ou 3.11) varrendo os diretórios comuns do Windows
set "PYTHON_EXE="

:: --- CHECAGEM 1: Usuário local (Instalação padrão do usuário) ---
if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
    set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    goto python_found
)
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    goto python_found
)

:: --- CHECAGEM 2: Arquivos de Programas de 64 bits (Instalação global) ---
if exist "%ProgramFiles%\Python310\python.exe" (
    set "PYTHON_EXE=%ProgramFiles%\Python310\python.exe"
    goto python_found
)
if exist "%ProgramFiles%\Python311\python.exe" (
    set "PYTHON_EXE=%ProgramFiles%\Python311\python.exe"
    goto python_found
)

:: --- CHECAGEM 3: Arquivos de Programas de 32 bits ---
if exist "%ProgramFiles(x86)%\Python310\python.exe" (
    set "PYTHON_EXE=%ProgramFiles(x86)%\Python310\python.exe"
    goto python_found
)
if exist "%ProgramFiles(x86)%\Python311\python.exe" (
    set "PYTHON_EXE=%ProgramFiles(x86)%\Python311\python.exe"
    goto python_found
)

:: --- CHECAGEM 4: Raiz do Sistema (C:\Python310 ou C:\Python311) ---
if exist "C:\Python310\python.exe" (
    set "PYTHON_EXE=C:\Python310\python.exe"
    goto python_found
)
if exist "C:\Python311\python.exe" (
    set "PYTHON_EXE=C:\Python311\python.exe"
    goto python_found
)

:: --- CHECAGEM 5: Verificar se o comando global 'python' responde com versão compatível (não-3.14) ---
python --version >nul 2>&1
if errorlevel 1 goto download_python

:: Captura a versão do python padrão do sistema
for /f "tokens=2" %%v in ('python --version 2^>&1') do set "PY_VER=%%v"
:: Se a versão começar com 3.10 ou 3.11, podemos usar o comando global
echo !PY_VER! | findstr /r "^3\.10\." >nul
if not errorlevel 1 (
    set "PYTHON_EXE=python"
    goto python_found
)
echo !PY_VER! | findstr /r "^3\.11\." >nul
if not errorlevel 1 (
    set "PYTHON_EXE=python"
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

:: Verifica novamente após o instalador
if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
    set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    goto python_found
)
if exist "%ProgramFiles%\Python310\python.exe" (
    set "PYTHON_EXE=%ProgramFiles%\Python310\python.exe"
    goto python_found
)
python --version >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_EXE=python"
    goto python_found
)
echo [X] O Python nao foi detectado apos a instalacao.
goto end_error

:python_found
echo [✔️] Python estavel selecionado para o projeto: %PYTHON_EXE%
echo.

:: 2. Sempre recriar a .venv se houver qualquer suspeita de vínculo com versão incorreta
if exist ".venv" (
    echo [*] Limpando pasta .venv existente para evitar conflitos de versao...
    rmdir /s /q ".venv"
)

:create_venv
echo [*] Criando novo ambiente virtual (.venv) usando a versao estavel do Python...
"%PYTHON_EXE%" -m venv .venv
if errorlevel 1 goto venv_error
echo [✔️] Ambiente virtual criado com sucesso!
goto install_deps

:venv_error
echo [X] Erro ao criar o ambiente virtual (.venv).
goto end_error

:install_deps
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
