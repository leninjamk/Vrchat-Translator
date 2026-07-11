"""
Lista de aplicativos com sessao de audio ativa no Windows, usada pelo seletor
de "Aplicativo especifico" da fala recebida.

IMPORTANTE sobre threads: as funcoes deste modulo usam pycaw (COM). Seguindo a
mesma convencao ja adotada em core/audio_device_manager.py ("Nao usa COM/pycaw"
no monitor de dispositivos, que roda em background), list_audio_session_apps()
SO deve ser chamada a partir da thread principal (Qt/GUI) — construcao da UI e
clique no botao "Atualizar lista". find_pid_by_executable() usa so psutil (sem
COM) e e segura de chamar de qualquer thread, inclusive a de reconexao do
ApplicationAudioSource.
"""
from dataclasses import dataclass
from typing import List, Optional

import psutil


@dataclass
class AudioSessionApp:
    pid: int
    executable: str      # ex: "VRChat.exe"
    display_name: str    # ex: "Vrchat"
    is_active: bool


def _friendly_name(executable: str) -> str:
    """Heuristica simples: 'VRChat.exe' -> 'Vrchat'. Sem ler recursos do
    executavel (FileDescription/ProductName) de proposito — fora de escopo
    da primeira versao, ver plano."""
    base = executable[:-4] if executable.lower().endswith(".exe") else executable
    base = base.replace("_", " ").replace("-", " ").strip()
    return base.title() if base else executable


def list_audio_session_apps() -> List[AudioSessionApp]:
    """Enumera processos com sessao de audio (pycaw). SO chamar da thread da
    GUI (ver aviso no topo do arquivo). Sessoes 'Expired' sao descartadas (a
    sessao/processo ja nao existe de verdade). Deduplica por executavel
    (case-insensitive), preferindo a entrada ativa em caso de empate.
    Ordenado: ativos primeiro, depois por nome amigavel."""
    from pycaw.utils import AudioUtilities
    from pycaw.constants import AudioSessionState

    by_exe = {}
    try:
        sessions = AudioUtilities.GetAllSessions()
    except Exception:
        return []

    for session in sessions:
        try:
            if session.State == AudioSessionState.Expired:
                continue
            proc = session.Process
            if proc is None:
                continue
            executable = proc.name()
            if not executable:
                continue
            is_active = session.State == AudioSessionState.Active
            key = executable.lower()
            existing = by_exe.get(key)
            if existing is not None and existing.is_active and not is_active:
                continue
            by_exe[key] = AudioSessionApp(
                pid=proc.pid,
                executable=executable,
                display_name=_friendly_name(executable),
                is_active=is_active,
            )
        except Exception:
            continue

    apps = list(by_exe.values())
    apps.sort(key=lambda a: (not a.is_active, a.display_name.lower()))
    return apps


def find_pid_by_executable(executable_name: str) -> Optional[int]:
    """Thread-safe pra qualquer thread (so psutil, sem COM). Primeiro
    processo vivo encontrado com esse nome de executavel vence."""
    target = (executable_name or "").lower()
    if not target:
        return None
    try:
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                name = proc.info.get("name") or ""
            except Exception:
                continue
            if name.lower() == target:
                return proc.info.get("pid")
    except Exception:
        pass
    return None
