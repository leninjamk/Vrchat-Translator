import os
import sys
import subprocess
import urllib.request

def get_python_exe():
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    program_files = os.environ.get("ProgramFiles", "")
    program_files_x86 = os.environ.get("ProgramFiles(x86)", "")
    
    paths = [
        os.path.join(local_app_data, r"Programs\Python\Python310\python.exe"),
        os.path.join(local_app_data, r"Programs\Python\Python311\python.exe"),
        os.path.join(program_files, r"Python310\python.exe"),
        os.path.join(program_files, r"Python311\python.exe"),
        os.path.join(program_files_x86, r"Python310\python.exe"),
        os.path.join(program_files_x86, r"Python311\python.exe"),
        r"C:\Python310\python.exe",
        r"C:\Python311\python.exe",
    ]
    
    for path in paths:
        if os.path.exists(path):
            return path
            
    ver = sys.version_info
    if ver.major == 3 and ver.minor in (10, 11):
        return sys.executable
        
    return None

def download_python():
    print("[!] Python 3.10/3.11 estavel nao foi localizado.")
    print("[*] Baixando instalador do Python 3.10.11 do site oficial...")
    url = "https://www.python.org/ftp/python/3.10.11/python-3.10.11-amd64.exe"
    installer = "python_installer.exe"
    try:
        urllib.request.urlretrieve(url, installer)
        print("[OK] Download concluido!")
        print("[*] Iniciando instalador visual. IMPORTANTE: Marque 'Add Python to PATH' na instalacao!")
        subprocess.run([installer], check=True)
        if os.path.exists(installer):
            os.remove(installer)
    except Exception as e:
        print(f"[X] Erro ao baixar/instalar o Python: {e}")
        input("Pressione Enter para fechar...")
        sys.exit(1)

def main():
    print("===================================================")
    print("             Instalador de Dependencias")
    print("             Translator By: LeNinjaMK")
    print("===================================================")
    print()

    python_exe = get_python_exe()
    if not python_exe:
        download_python()
        python_exe = get_python_exe()
        if not python_exe:
            print("[X] Python nao foi localizado apos a instalacao. Por favor, reinicie e tente de novo.")
            input("Pressione Enter para fechar...")
            sys.exit(1)
            
    print(f"[OK] Python estavel selecionado: {python_exe}")
    print()

    # 2. Criar ou recriar a .venv
    venv_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".venv")
    if os.path.exists(venv_dir):
        print("[*] Limpando pasta .venv antiga...")
        subprocess.run(f'rmdir /s /q "{venv_dir}"', shell=True)

    print("[*] Criando ambiente virtual (.venv)...")
    try:
        subprocess.run([python_exe, "-m", "venv", venv_dir], check=True)
        print("[OK] Ambiente virtual criado com sucesso!")
    except Exception as e:
        print(f"[X] Erro ao criar .venv: {e}")
        input("Pressione Enter para fechar...")
        sys.exit(1)

    # 3. Instalar dependências usando o python do .venv
    venv_python = os.path.join(venv_dir, r"Scripts\python.exe")
    print()
    print("[*] Instalando pacotes necessarios (requirements.txt)...")
    try:
        subprocess.run([venv_python, "-m", "pip", "install", "--upgrade", "pip"], check=True)
        req_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "requirements.txt")
        subprocess.run([venv_python, "-m", "pip", "install", "-r", req_file], check=True)
        
        print()
        print("===================================================")
        print("[OK] INSTALACAO CONCLUIDA COM SUCESSO!")
        print("Agora voce ja pode fechar esta janela e rodar o 'Run.bat'")
        print("===================================================")
    except Exception as e:
        print(f"\n[X] Erro ao instalar dependencias: {e}")
        
    print()
    input("Pressione qualquer tecla para concluir...")

if __name__ == "__main__":
    main()
