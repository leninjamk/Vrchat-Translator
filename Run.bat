@echo off
:: Garante que o script roda no diretorio onde o arquivo .bat esta localizado
cd /d "%~dp0"

:: Executa o aplicativo de forma desacoplada e limpa usando a .venv local
start "" ".venv\Scripts\pythonw.exe" "ui\app.py"

:: Fecha o CMD imediatamente
exit
