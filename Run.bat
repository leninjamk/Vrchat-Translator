@echo off
cd /d "C:\Users\AnonymousBR\Desktop\Projetos Python\Tradutor 2.0"

:: Executa o aplicativo de forma desacoplada e limpa
start "" ".venv\Scripts\pythonw.exe" "ui\app.py"

:: Fecha o CMD imediatamente
exit
