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


def run_silent(cmd, label):
    """Executa um comando mostrando apenas um label amigavel (sem paths absolutos)."""
    print(f"    {label}...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 and result.stderr:
        # Mostra erros relevantes mas sem paths absolutos do sistema
        lines = [l for l in result.stderr.splitlines()
                 if not l.strip().startswith(">") and "WARNING" not in l]
        if lines:
            print("    " + "\n    ".join(lines[:5]))
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
        print("    Se persistir, instale em: https://www.python.org/downloads/")
        sys.exit(1)

    # Extrai apenas a versao para exibir (sem expor o caminho completo)
    try:
        ver_result = subprocess.run([python_exe, "--version"],
                                    capture_output=True, text=True, timeout=5)
        py_version = ver_result.stdout.strip() or ver_result.stderr.strip()
    except Exception:
        py_version = "Python (encontrado)"

    print(f"[OK] {py_version} encontrado!")
    print()

    # ── 2. Criar/recriar .venv ────────────────────────────────────────────────
    if os.path.exists(venv_dir):
        print("[*] Removendo ambiente virtual anterior...")
        shutil.rmtree(venv_dir, ignore_errors=True)
        if os.path.exists(venv_dir):
            subprocess.run(f'rmdir /s /q "{venv_dir}"', shell=True,
                           capture_output=True)

    print("[*] Criando ambiente virtual (.venv)...")
    result = subprocess.run([python_exe, "-m", "venv", venv_dir],
                            capture_output=True, text=True)
    if result.returncode != 0:
        print("[X] ERRO: Falha ao criar ambiente virtual.")
        if result.stderr:
            print("   ", result.stderr[:200])
        sys.exit(1)
    print("[OK] Ambiente virtual criado!")
    print()

    # ── 3. Caminhos do venv ───────────────────────────────────────────────────
    venv_python = os.path.join(venv_dir, "Scripts", "python.exe")

    if not os.path.isfile(venv_python):
        print("[X] ERRO: python.exe nao encontrado no .venv.")
        sys.exit(1)

    # ── 4. Atualizar pip ──────────────────────────────────────────────────────
    print("[*] Atualizando pip...")
    subprocess.run([venv_python, "-m", "pip", "install", "--upgrade", "pip", "--quiet"],
                   capture_output=True)
    print("[OK] Pip atualizado!")
    print()

    # ── 5. Instalar dependencias ──────────────────────────────────────────────
    if not os.path.isfile(req_file):
        print("[X] ERRO: requirements.txt nao encontrado!")
        sys.exit(1)

    print("[*] Instalando dependencias (requirements.txt)...")
    print("    Isso pode levar alguns minutos...")
    print()

    import time as _time

    max_attempts = 3
    result = None
    for attempt in range(1, max_attempts + 1):
        pip_cmd = [venv_python, "-m", "pip", "install", "-r", req_file]
        if attempt > 1:
            # Em tentativas seguintes evita cache (pode estar com arquivo
            # parcialmente bloqueado pelo antivirus na tentativa anterior)
            pip_cmd.append("--no-cache-dir")
            print(f"    Tentativa {attempt}/{max_attempts}...")

        # Roda com output visivel para o usuario acompanhar o progresso
        result = subprocess.run(pip_cmd)

        if result.returncode == 0:
            break

        if attempt < max_attempts:
            print()
            print("    [!] Falhou, isso pode ser o antivirus bloqueando")
            print("        arquivos temporariamente. Tentando de novo em 5s...")
            print()
            _time.sleep(5)

    if result.returncode != 0:
        print()
        print("[X] ERRO: Falha ao instalar dependencias apos varias tentativas.")
        print("    Isso geralmente e causado pelo antivirus (inclusive o Windows")
        print("    Defender) bloqueando temporariamente os arquivos durante a")
        print("    instalacao. Tente:")
        print("      1) Desativar a protecao em tempo real do antivirus e rodar")
        print("         o instalador de novo, ou")
        print("      2) Clicar com o botao direito no instalador e escolher")
        print("         'Executar como administrador'.")
        print("    Se persistir, verifique sua conexao com a internet.")
        sys.exit(1)

    # ── 6. Voz local Kokoro (OPCIONAL, gratuita, melhor qualidade) ─────────────
    # Best-effort de proposito: as dependencias essenciais ja instalaram com
    # sucesso acima (nunca chega aqui se o passo 5 falhou). Se o Kokoro nao
    # instalar (Python >=3.13, sem internet, etc.), o app funciona normal
    # com o edge-tts de sempre — so nao mostra as vozes Kokoro extras.
    #
    # De proposito SEM os extras "misaki[ja,zh]" (vozes japonesa/mandarim do
    # Kokoro) aqui: eles puxam o pacote pyopenjtalk, que precisa COMPILAR uma
    # extensao nativa (exige Visual Studio instalado) — a grande maioria dos
    # usuarios nao tem isso, e incluir esses extras no MESMO comando faz o
    # pip falhar a instalacao INTEIRA (nada instala, nem o Kokoro basico).
    # As vozes Kokoro de portugues/ingles/espanhol/frances/italiano/hindi nao
    # precisam disso e instalam normal. Sem o pyopenjtalk, as vozes japonesa/
    # mandarim do Kokoro especificamente ficam indisponiveis e caem sozinhas
    # pro edge-tts (ver core/tts.py) — quem quiser essas duas pode instalar
    # manualmente depois com Visual Studio Build Tools + "misaki[ja,zh]".
    print("[*] Instalando voz local Kokoro (opcional, pode ser pulado)...")
    kokoro_result = subprocess.run(
        [venv_python, "-m", "pip", "install", "kokoro", "misaki", "soundfile", "--quiet"],
        capture_output=True, text=True,
    )
    if kokoro_result.returncode == 0:
        print("[OK] Voz local Kokoro instalada!")
    else:
        print("    [!] Voz local Kokoro não instalada (opcional — o app")
        print("        continua funcionando normal com as vozes de sempre).")
    print()

    # ── 7. Sucesso ────────────────────────────────────────────────────────────
    print()
    print("=" * 51)
    print("[OK] INSTALACAO CONCLUIDA COM SUCESSO!")
    print()
    print("     Feche esta janela e execute o Run.bat")
    print("=" * 51)
    print()
    print("Esta janela fecha automaticamente em 5 segundos...")

    import time
    time.sleep(5)


if __name__ == "__main__":
    main()
