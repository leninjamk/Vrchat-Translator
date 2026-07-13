"""
Ponto de entrada principal do Translator by LeNinjaMK.
Execute este arquivo diretamente: python run.py
"""
import sys
import os

# Garante que o diretorio raiz do projeto esteja no path de importacao,
# independente de onde o script for chamado.
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Build empacotado (PyInstaller --windowed) roda sem console: sys.stdout/
# stderr viram None, e qualquer print() (varios no projeto usam emojis nos
# logs, ex: "🎧 OUTPUT fixado") derruba o app na hora com AttributeError. Ate
# quando existem (saida redirecionada pra arquivo, por exemplo), o Windows as
# vezes escolhe um encoding sem suporte a emoji (cp1252), quebrando com
# UnicodeEncodeError. Nesse caso sem console, manda pra um arquivo de log ao
# lado do .exe (nunca pra os.devnull) — assim, se o app fechar sozinho sem
# aviso nenhum, da pra abrir log.txt depois e ver o que aconteceu. Um log()
# que falha nunca deve impedir o app de abrir (por isso o try/except).
if sys.stdout is None or sys.stderr is None:
    log_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else ROOT
    try:
        log_file = open(os.path.join(log_dir, "log.txt"), "w", encoding="utf-8", errors="replace")
    except Exception:
        log_file = open(os.devnull, "w", encoding="utf-8")
    if sys.stdout is None:
        sys.stdout = log_file
    if sys.stderr is None:
        sys.stderr = log_file
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from ui.app import main

if __name__ == "__main__":
    main()
