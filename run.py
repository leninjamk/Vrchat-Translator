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

from ui.app import main

if __name__ == "__main__":
    main()
