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

import tkinter as tk
from ui.app import App

if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
