@echo off
:: Garante que o script roda no diretorio onde o .bat esta localizado
cd /d "%~dp0"

:: Verifica se o ambiente virtual existe
if not exist ".venv\Scripts\pythonw.exe" (
    echo [ERRO] Ambiente virtual nao encontrado!
    echo Execute o Install.bat primeiro.
    pause
    exit /b 1
)

:: Inicia o app sem janela de console usando run.py como ponto de entrada
start "" ".venv\Scripts\pythonw.exe" "run.py"

:: Fecha o CMD imediatamente
exit
