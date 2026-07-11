import asyncio
import os
import re
import tempfile
import threading

import edge_tts
from core.singleton import engine
from core.voices import VOICES
from core.echo_guard import echo_guard

tts_lock = threading.Lock()


def _normalize_lang(lang: str) -> str:
    lang = (lang or "en").strip()

    fix = {
        "zh": "zh-CN",
        "cn": "zh-CN",
        "zh-cn": "zh-CN",
        "zh-tw": "zh-TW",
        "tw": "zh-TW",
        "jp": "ja",
        "kr": "ko",
    }

    return fix.get(lang.lower(), lang)


def _clean_text(text: str) -> str:
    text = str(text or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text


async def _generate(text: str, voice: str, path: str, pitch: int = 0) -> None:
    # O pitch é recebido como inteiro (-50 a 50). Formatamos no padrão do edge-tts, ex: "+10Hz" ou "-15Hz".
    pitch_str = f"{pitch:+}Hz"
    communicate = edge_tts.Communicate(text=text, voice=voice, pitch=pitch_str)
    await communicate.save(path)


def speak(text, lang="en", pitch=0, engine_instance=None):
    """engine_instance: qual AudioEngine (qual dispositivo de saida) tocar o
    audio. Default None usa o engine global (minha fala). A fala recebida
    passa um engine proprio (core.singleton.received_tts_engine) pra poder
    usar um dispositivo de saida diferente — ver core/singleton.py."""
    text = _clean_text(text)
    if not text:
        print("❌ TTS vazio ignorado")
        return

    lang = _normalize_lang(lang)
    voice = VOICES.get(lang, VOICES["en"])
    target_engine = engine_instance or engine

    with tts_lock:
        tmp_path = None
        try:
            fd, tmp_path = tempfile.mkstemp(suffix=".mp3")
            os.close(fd)

            asyncio.run(_generate(text, voice, tmp_path, pitch))

            if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) < 1000:
                print("❌ TTS error: audio vazio")
                return

            echo_guard.mark_tts_start()
            try:
                target_engine.play(tmp_path)
            finally:
                echo_guard.mark_tts_end()

        except Exception as e:
            print("❌ TTS error:", e)

        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except:
                    pass