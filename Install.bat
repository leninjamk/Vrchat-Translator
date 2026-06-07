@echo off
cd /d "%~dp0"

:: Executa o instalador Python de forma direta
python install_project.py

:: Garante que se der algum erro catastrófico na chamada, o CMD não feche sem mostrar
if errorlevel 1 (
    echo [X] Erro ao iniciar o instalador Python.
    pause
)
