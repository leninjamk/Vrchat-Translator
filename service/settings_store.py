"""
Persistência de settings.json — portado literalmente de ui/app.py:41-119
(mesma matemática de path, mesmo formato JSON). Isso garante que o
settings.json de quem já usa o app continua resolvendo pro mesmo arquivo e
sendo lido sem migração. Único dono do arquivo agora é este processo (o
frontend só fala com ele via IPC settings.get/settings.set — ver ipc_server.py).
"""
import json
import os
import sys

if getattr(sys, "frozen", False):
    _APP_ROOT = os.path.dirname(sys.executable)
else:
    _APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS_FILE = os.path.join(_APP_ROOT, "settings.json")

# Schema completo (~25 chaves legadas do app PySide6 + 2 novas de shader,
# adição pura pra funcionalidade extra pedida pelo usuário — nunca remove
# nem muda o significado de nenhuma chave existente).
DEFAULTS = {
    "mic": "",
    "out": "",
    "from_lang": "Português (BR)",
    "to_lang": "Inglês (US)",
    "beep": True,
    "tts_voice": True,
    "chatbox_mode": "Original + tradução",
    "panel_open": False,
    "settings_open": False,
    "window_x": None,
    "window_y": None,
    "listen_others": False,
    "received_device": "",
    "speaker_audio_source_mode": "full_device",
    "speaker_target_executable": "",
    "received_langs": ["pt"],
    "received_tts": False,
    "received_tts_output": "",
    "overlay_enabled": False,
    "overlay_backend": "Desktop (janela flutuante)",
    "overlay_opacity": 90,
    "overlay_duration": 6,
    "overlay_always_visible": False,
    "overlay_font_size": 20,
    "overlay_max_lines": 4,
    "overlay_auto_steamvr": True,  # detecção automática de SteamVR (pedido do usuário)
    "mute_sync": False,
    "mute_pause_mic": False,  # legado, não usado mais pela UI — mantido só por compatibilidade
    "voice_overrides": {},
    # "digital_rain" | "rings" (presets embutidos, definidos só no frontend)
    # ou o id de um preset salvo em shader_presets.
    "shader_preset": "digital_rain",
    "shader_presets": [],  # [{id, name, source}, ...] — presets de shader salvos pelo usuário
    # Liga/desliga o fundo animado (pedido do usuario: saida de seguranca em
    # PC fraco - o shader padrao faz raymarching de 30 iteracoes por pixel).
    "shader_enabled": True,
    "ui_language": "pt",  # idioma da INTERFACE (ver frontend/src/i18n/index.ts::UiLanguage) — não é idioma de tradução de fala
    # Aba "OSC" (pedido do usuário) — porta de ENVIO (chatbox) e de ESCUTA
    # (mute sync) configuráveis; defaults iguais aos hardcoded que já
    # existiam em config.py/core/vrchat_osc_receiver.py.
    "osc_send_ip": "127.0.0.1",
    "osc_send_port": 9000,
    "osc_receive_port": 9001,
    # Estilo de fonte Unicode (pedido do usuario) aplicado SO no texto
    # enviado ao chatbox do VRChat (ver core/text_styles.py) - a Conversa do
    # app e o overlay continuam mostrando o texto normal, sem estilo.
    "chatbox_text_style": "normal",
}


def load_settings() -> dict:
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            merged = dict(DEFAULTS)
            merged.update(loaded)
            return merged
        except Exception:
            pass
    return dict(DEFAULTS)


def save_settings(settings: dict) -> None:
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4, ensure_ascii=False)
    except Exception:
        pass
