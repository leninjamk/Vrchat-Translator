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

:: Versoes mais novas que 3.12 ficam de fora de proposito: pacotes nativos
:: (pyaudiowpatch, numpy...) nem sempre tem wheel pronta pra Python recem-
:: lancado, e sem isso o pip tenta COMPILAR do zero - o que exige Visual C++
:: Build Tools que quase ninguem tem instalado, e quebra a instalacao inteira
:: (ja aconteceu de verdade com um usuario em Python 3.14).
if "!PYTHON_EXE!"=="" if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if "!PYTHON_EXE!"=="" if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if "!PYTHON_EXE!"=="" if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
if "!PYTHON_EXE!"=="" if exist "%LOCALAPPDATA%\Programs\Python\Python39\python.exe"  set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python39\python.exe"

if "!PYTHON_EXE!"=="" if exist "%ProgramFiles%\Python312\python.exe" set "PYTHON_EXE=%ProgramFiles%\Python312\python.exe"
if "!PYTHON_EXE!"=="" if exist "%ProgramFiles%\Python311\python.exe" set "PYTHON_EXE=%ProgramFiles%\Python311\python.exe"
if "!PYTHON_EXE!"=="" if exist "%ProgramFiles%\Python310\python.exe" set "PYTHON_EXE=%ProgramFiles%\Python310\python.exe"
if "!PYTHON_EXE!"=="" if exist "%ProgramFiles%\Python39\python.exe"  set "PYTHON_EXE=%ProgramFiles%\Python39\python.exe"

if "!PYTHON_EXE!"=="" if exist "C:\Python312\python.exe" set "PYTHON_EXE=C:\Python312\python.exe"
if "!PYTHON_EXE!"=="" if exist "C:\Python311\python.exe" set "PYTHON_EXE=C:\Python311\python.exe"
if "!PYTHON_EXE!"=="" if exist "C:\Python310\python.exe" set "PYTHON_EXE=C:\Python310\python.exe"
if "!PYTHON_EXE!"=="" if exist "C:\Python39\python.exe"  set "PYTHON_EXE=C:\Python39\python.exe"

:: Tenta o python do PATH (filtra alias da Microsoft Store e versoes sem suporte)
if "!PYTHON_EXE!"=="" (
    for /f "tokens=*" %%i in ('where python 2^>nul') do (
        if "!PYTHON_EXE!"=="" (
            echo %%i | findstr /i "WindowsApps" >nul 2>&1
            if !errorlevel! neq 0 (
                for /f "tokens=2" %%v in ('"%%i" --version 2^>^&1') do (
                    set "PYVER=%%v"
                    if "!PYVER:~0,3!"=="3.9" set "PYTHON_EXE=%%i"
                    if "!PYVER:~0,4!"=="3.10" set "PYTHON_EXE=%%i"
                    if "!PYVER:~0,4!"=="3.11" set "PYTHON_EXE=%%i"
                    if "!PYVER:~0,4!"=="3.12" set "PYTHON_EXE=%%i"
                )
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
        exit /b 1
    )

    echo [OK] Download concluido!
    echo [*] Instalando Python silenciosamente...

    "!PY_INSTALLER!" /quiet /norestart InstallAllUsers=0 PrependPath=1 Include_test=0 Include_launcher=1 Include_pip=1

    set "PY_ERR=!errorlevel!"
    del "!PY_INSTALLER!" >nul 2>&1

    if !PY_ERR! neq 0 if !PY_ERR! neq 3010 (
        echo [X] ERRO: Falha na instalacao do Python ^(codigo !PY_ERR!^).
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

:: -u desliga o buffer de stdout/stderr do Python — sem isso, quando a saida
:: e redirecionada pra um arquivo (em vez de um console de verdade, caso do
:: Exec escondido do installer.iss), o Python junta varios prints num bloco
:: so e escreve tudo de uma vez, fazendo o log da tela do instalador parecer
:: travado por minutos e depois "despejar" tudo no final.
"!PYTHON_EXE!" -u "%~dp0install_project.py"

if !errorlevel! neq 0 (
    echo.
    echo [X] ERRO durante a instalacao das dependencias.
    echo     Veja a mensagem acima para mais detalhes.
    exit /b 1
)
echo.

endlocal
