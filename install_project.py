"""
Instalador de dependencias - VRChat Translator By LeNinjaMK
Execucao 100% autonoma: sem interacao do usuario.
"""
import os
import sys
import subprocess
import shutil


def get_python_exe():
    """
    Localiza um Python 3.9+ valido no sistema.
    Ignora o alias da Microsoft Store (WindowsApps).
    """
    local_app_data  = os.environ.get("LOCALAPPDATA", "")
    program_files   = os.environ.get("ProgramFiles", "")
    program_files86 = os.environ.get("ProgramFiles(x86)", "")
    user_profile    = os.environ.get("USERPROFILE", "")

    versions = ["313", "312", "311", "310", "39"]
    candidates = []

    for v in versions:
        candidates += [
            os.path.join(local_app_data, f"Programs\\Python\\Python{v}\\python.exe"),
            os.path.join(user_profile,   f"AppData\\Local\\Programs\\Python\\Python{v}\\python.exe"),
            os.path.join(program_files,  f"Python{v}\\python.exe"),
            os.path.join(program_files86, f"Python{v}\\python.exe"),
            f"C:\\Python{v}\\python.exe",
        ]

    for path in candidates:
        if os.path.isfile(path):
            return path

    # Executavel atual (se rodar via outro Python valido)
    if sys.version_info >= (3, 9) and "WindowsApps" not in sys.executable:
        return sys.executable

    # Ultimo recurso: python no PATH, excluindo alias da Store
    for cmd in ("python", "python3"):
        found = shutil.which(cmd)
        if found and "WindowsApps" not in found:
            try:
                r = subprocess.run([found, "--version"],
                                   capture_output=True, text=True, timeout=5)
                if r.returncode == 0:
                    return found
            except Exception:
                pass

    return None


def run(cmd, **kwargs):
    """Executa um comando e retorna o codigo de saida."""
    print(f"    > {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd, **kwargs)
    return result.returncode


def main():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    venv_dir = os.path.join(root_dir, ".venv")
    req_file = os.path.join(root_dir, "requirements.txt")

    print()
    print("=" * 51)
    print("        Instalador de Dependencias")
    print("        VRChat Translator By: LeNinjaMK")
    print("=" * 51)
    print()

    # ── 1. Localizar Python ───────────────────────────────────────────────────
    python_exe = get_python_exe()

    if not python_exe:
        print("[X] ERRO: Python 3.9+ nao encontrado.")
        print("    O Install.bat deveria ter instalado automaticamente.")
        print("    Se o problema persistir, instale manualmente:")
        print("    https://www.python.org/downloads/")
        sys.exit(1)

    print(f"[OK] Python encontrado: {python_exe}")
    print()

    # ── 2. Criar/recriar .venv ────────────────────────────────────────────────
    if os.path.exists(venv_dir):
        print("[*] Removendo ambiente virtual anterior...")
        shutil.rmtree(venv_dir, ignore_errors=True)
        if os.path.exists(venv_dir):
            # rmtree pode falhar no Windows; usa cmd como fallback
            subprocess.run(f'rmdir /s /q "{venv_dir}"', shell=True)

    print("[*] Criando novo ambiente virtual (.venv)...")
    code = run([python_exe, "-m", "venv", venv_dir])
    if code != 0:
        print("[X] ERRO: Falha ao criar ambiente virtual.")
        sys.exit(1)
    print("[OK] Ambiente virtual criado!")
    print()

    # ── 3. Caminhos do venv ───────────────────────────────────────────────────
    venv_python = os.path.join(venv_dir, "Scripts", "python.exe")
    venv_pip    = os.path.join(venv_dir, "Scripts", "pip.exe")

    if not os.path.isfile(venv_python):
        print("[X] ERRO: python.exe nao encontrado no .venv criado.")
        sys.exit(1)

    # ── 4. Atualizar pip ─────────────────────────────────────────────────────
    print("[*] Atualizando pip...")
    run([venv_python, "-m", "pip", "install", "--upgrade", "pip", "--quiet"])
    print()

    # ── 5. Instalar dependencias ──────────────────────────────────────────────
    if not os.path.isfile(req_file):
        print("[X] ERRO: requirements.txt nao encontrado!")
        sys.exit(1)

    print("[*] Instalando dependencias (requirements.txt)...")
    print("    Isso pode levar alguns minutos...")
    print()

    code = run([venv_python, "-m", "pip", "install", "-r", req_file])

    if code != 0:
        print()
        print("[X] ERRO: Falha ao instalar dependencias.")
        print("    Verifique sua conexao com a internet e tente novamente.")
        sys.exit(1)

    # ── 6. Sucesso ────────────────────────────────────────────────────────────
    print()
    print("=" * 51)
    print("[OK] INSTALACAO CONCLUIDA COM SUCESSO!")
    print()
    print("     Agora feche esta janela e execute:")
    print("     Run.bat")
    print("=" * 51)
    print()

    # Aguarda 5 segundos e fecha automaticamente
    print("Esta janela fecha automaticamente em 5 segundos...")
    import time
    time.sleep(5)


if __name__ == "__main__":
    main()
