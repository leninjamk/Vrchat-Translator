@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title Instalando Translator By LeNinjaMK...

echo.
echo ===================================================
echo      Instalador Automatico - VRChat Translator
echo               By: LeNinjaMK
echo ===================================================
echo.

:: ─────────────────────────────────────────────────────────────────────────────
::  PASSO 1: Procurar Python instalado (ignora alias da Microsoft Store)
:: ─────────────────────────────────────────────────────────────────────────────
set "PYTHON_EXE="

echo [*] Procurando Python no sistema...

for %%V in (313 312 311 310 39) do (
    if "!PYTHON_EXE!"=="" (
        for %%P in (
            "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe"
            "%ProgramFiles%\Python%%V\python.exe"
            "%ProgramFiles(x86)%\Python%%V\python.exe"
            "C:\Python%%V\python.exe"
            "%USERPROFILE%\AppData\Local\Programs\Python\Python%%V\python.exe"
        ) do (
            if "!PYTHON_EXE!"=="" (
                if exist %%P (
                    set "PYTHON_EXE=%%~P"
                )
            )
        )
    )
)

:: Tenta via PATH mas filtra o alias da Microsoft Store
if "!PYTHON_EXE!"=="" (
    for /f "tokens=*" %%i in ('where python 2^>nul') do (
        if "!PYTHON_EXE!"=="" (
            echo %%i | findstr /i "WindowsApps" >nul 2>&1
            if !errorlevel! neq 0 (
                "%%i" --version >nul 2>&1
                if !errorlevel! == 0 (
                    set "PYTHON_EXE=%%i"
                )
            )
        )
    )
)

:: ─────────────────────────────────────────────────────────────────────────────
::  PASSO 2: Python nao encontrado → baixa e instala automaticamente
:: ─────────────────────────────────────────────────────────────────────────────
if "!PYTHON_EXE!"=="" (
    echo [!] Python nao encontrado.
    echo [*] Baixando Python 3.10.11 automaticamente...
    echo     Isso pode levar alguns minutos dependendo da sua internet.
    echo.

    set "PY_INSTALLER=%TEMP%\python_tradutor_setup.exe"
    set "PY_URL=https://www.python.org/ftp/python/3.10.11/python-3.10.11-amd64.exe"

    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
        "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; $wc = New-Object Net.WebClient; Write-Host '    Baixando...'; $wc.DownloadFile('!PY_URL!', '!PY_INSTALLER!'); Write-Host '[OK] Download concluido!'"

    if !errorlevel! neq 0 (
        echo.
        echo [X] ERRO: Falha ao baixar o Python.
        echo     Verifique sua conexao com a internet e tente novamente.
        echo.
        pause
        exit /b 1
    )

    echo [*] Instalando Python silenciosamente (aguarde)...

    "!PY_INSTALLER!" /quiet /norestart ^
        InstallAllUsers=0 ^
        PrependPath=1 ^
        Include_test=0 ^
        Include_launcher=1 ^
        Include_pip=1

    set "PY_INSTALL_ERR=!errorlevel!"
    del "!PY_INSTALLER!" >nul 2>&1

    :: Codigo 3010 = instalou OK, requer reboot (mas funciona sem reiniciar)
    if !PY_INSTALL_ERR! neq 0 (
        if !PY_INSTALL_ERR! neq 3010 (
            echo [X] ERRO: Instalacao do Python falhou ^(codigo !PY_INSTALL_ERR!^).
            echo     Tente executar o instalador manualmente: https://www.python.org/downloads/
            pause
            exit /b 1
        )
    )

    echo [OK] Python instalado com sucesso!
    echo.

    :: Procura o Python recem instalado
    for %%V in (310 311 312 313) do (
        if "!PYTHON_EXE!"=="" (
            for %%P in (
                "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe"
                "%ProgramFiles%\Python%%V\python.exe"
            ) do (
                if "!PYTHON_EXE!"=="" (
                    if exist %%P set "PYTHON_EXE=%%~P"
                )
            )
        )
    )

    if "!PYTHON_EXE!"=="" (
        echo [X] Python instalado mas nao localizado.
        echo     Reinicie o computador e execute este instalador novamente.
        pause
        exit /b 1
    )
)

echo [OK] Python: !PYTHON_EXE!
echo.

:: ─────────────────────────────────────────────────────────────────────────────
::  PASSO 3: Rodar o instalador de dependencias Python (autonomo)
:: ─────────────────────────────────────────────────────────────────────────────
echo [*] Instalando dependencias do projeto...
echo.

"!PYTHON_EXE!" "%~dp0install_project.py"

if !errorlevel! neq 0 (
    echo.
    echo [X] ERRO durante a instalacao das dependencias.
    pause
    exit /b 1
)

endlocal
