import asyncio
import os
import re
import tempfile
import threading

import edge_tts
from core.singleton import engine
from core.voices import VOICES

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


async def _generate(text: str, voice: str, path: str) -> None:
    communicate = edge_tts.Communicate(text=text, voice=voice)
    await communicate.save(path)


def speak(text, lang="en", pitch=1.0):
    text = _clean_text(text)
    if not text:
        print("❌ TTS vazio ignorado")
        return

    lang = _normalize_lang(lang)
    voice = VOICES.get(lang, VOICES["en"])

    with tts_lock:
        tmp_path = None
        try:
            fd, tmp_path = tempfile.mkstemp(suffix=".mp3")
            os.close(fd)

            asyncio.run(_generate(text, voice, tmp_path))

            if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) < 1000:
                print("❌ TTS error: audio vazio")
                return

            engine.play(tmp_path)

        except Exception as e:
            print("❌ TTS error:", e)

        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except:
                    pass