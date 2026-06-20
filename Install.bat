@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title Instalador - VRChat Translator By LeNinjaMK

echo.
echo ===================================================
echo     Instalador Automatico - VRChat Translator
echo              By: LeNinjaMK
echo ===================================================
echo.

:: ─────────────────────────────────────────────────────────────────────────────
::  PASSO 1: Procurar Python (checa cada local individualmente)
:: ─────────────────────────────────────────────────────────────────────────────
echo [*] Procurando Python no sistema...
set "PYTHON_EXE="

if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if "!PYTHON_EXE!"=="" if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if "!PYTHON_EXE!"=="" if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if "!PYTHON_EXE!"=="" if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
if "!PYTHON_EXE!"=="" if exist "%LOCALAPPDATA%\Programs\Python\Python39\python.exe"  set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python39\python.exe"

if "!PYTHON_EXE!"=="" if exist "%ProgramFiles%\Python313\python.exe" set "PYTHON_EXE=%ProgramFiles%\Python313\python.exe"
if "!PYTHON_EXE!"=="" if exist "%ProgramFiles%\Python312\python.exe" set "PYTHON_EXE=%ProgramFiles%\Python312\python.exe"
if "!PYTHON_EXE!"=="" if exist "%ProgramFiles%\Python311\python.exe" set "PYTHON_EXE=%ProgramFiles%\Python311\python.exe"
if "!PYTHON_EXE!"=="" if exist "%ProgramFiles%\Python310\python.exe" set "PYTHON_EXE=%ProgramFiles%\Python310\python.exe"
if "!PYTHON_EXE!"=="" if exist "%ProgramFiles%\Python39\python.exe"  set "PYTHON_EXE=%ProgramFiles%\Python39\python.exe"

if "!PYTHON_EXE!"=="" if exist "C:\Python313\python.exe" set "PYTHON_EXE=C:\Python313\python.exe"
if "!PYTHON_EXE!"=="" if exist "C:\Python312\python.exe" set "PYTHON_EXE=C:\Python312\python.exe"
if "!PYTHON_EXE!"=="" if exist "C:\Python311\python.exe" set "PYTHON_EXE=C:\Python311\python.exe"
if "!PYTHON_EXE!"=="" if exist "C:\Python310\python.exe" set "PYTHON_EXE=C:\Python310\python.exe"
if "!PYTHON_EXE!"=="" if exist "C:\Python39\python.exe"  set "PYTHON_EXE=C:\Python39\python.exe"

:: Tenta o python do PATH (filtra alias da Microsoft Store)
if "!PYTHON_EXE!"=="" (
    for /f "tokens=*" %%i in ('where python 2^>nul') do (
        if "!PYTHON_EXE!"=="" (
            echo %%i | findstr /i "WindowsApps" >nul 2>&1
            if !errorlevel! neq 0 (
                "%%i" --version >nul 2>&1
                if !errorlevel! == 0 set "PYTHON_EXE=%%i"
            )
        )
    )
)

:: ─────────────────────────────────────────────────────────────────────────────
::  PASSO 2: Se nao achou Python → baixa e instala automaticamente
:: ─────────────────────────────────────────────────────────────────────────────
if "!PYTHON_EXE!"=="" (
    echo [!] Python nao encontrado.
    echo [*] Baixando Python 3.10.11 automaticamente...
    echo     Aguarde, isso pode demorar alguns minutos...
    echo.

    set "PY_URL=https://www.python.org/ftp/python/3.10.11/python-3.10.11-amd64.exe"
    set "PY_INSTALLER=%TEMP%\python_tradutor_setup.exe"

    powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object Net.WebClient).DownloadFile('!PY_URL!', '!PY_INSTALLER!')"

    if !errorlevel! neq 0 (
        echo.
        echo [X] ERRO: Nao foi possivel baixar o Python.
        echo     Verifique sua internet e tente de novo.
        echo.
        pause
        exit /b 1
    )

    echo [OK] Download concluido!
    echo [*] Instalando Python silenciosamente...

    "!PY_INSTALLER!" /quiet /norestart InstallAllUsers=0 PrependPath=1 Include_test=0 Include_launcher=1 Include_pip=1

    set "PY_ERR=!errorlevel!"
    del "!PY_INSTALLER!" >nul 2>&1

    if !PY_ERR! neq 0 if !PY_ERR! neq 3010 (
        echo [X] ERRO: Falha na instalacao do Python ^(codigo !PY_ERR!^).
        pause
        exit /b 1
    )

    echo [OK] Python instalado!
    echo.

    :: Procura novamente apos instalar
    if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    if "!PYTHON_EXE!"=="" if exist "%ProgramFiles%\Python310\python.exe" set "PYTHON_EXE=%ProgramFiles%\Python310\python.exe"

    if "!PYTHON_EXE!"=="" (
        echo [X] Python instalado mas nao localizado.
        echo     Reinicie o computador e execute o Install.bat novamente.
        pause
        exit /b 1
    )
)

echo [OK] Python encontrado: !PYTHON_EXE!
echo.

:: ─────────────────────────────────────────────────────────────────────────────
::  PASSO 3: Rodar o instalador de dependencias
:: ─────────────────────────────────────────────────────────────────────────────
echo [*] Instalando dependencias do projeto...
echo.

"!PYTHON_EXE!" "%~dp0install_project.py"

if !errorlevel! neq 0 (
    echo.
    echo [X] ERRO durante a instalacao das dependencias.
    echo     Veja a mensagem acima para mais detalhes.
    pause
    exit /b 1
)

endlocal
