import asyncio
import os
import re
import tempfile
import threading

import edge_tts
from core.singleton import engine
from core.voices import VOICES, normalize_lang_code, voice_options_for, find_voice_option
from core.echo_guard import echo_guard
from core import local_tts

tts_lock = threading.Lock()


def _clean_text(text: str) -> str:
    text = str(text or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text


async def _generate_edge(text: str, voice: str, path: str, pitch: int = 0) -> None:
    # O pitch é recebido como inteiro (-50 a 50). Formatamos no padrão do edge-tts, ex: "+10Hz" ou "-15Hz".
    pitch_str = f"{pitch:+}Hz"
    communicate = edge_tts.Communicate(text=text, voice=voice, pitch=pitch_str)
    await communicate.save(path)


def _default_edge_voice(lang: str) -> str:
    """Primeira opção edge-tts do idioma — usada de fallback quando uma voz
    Kokoro está selecionada mas o motor local falhou ou não está disponível."""
    for opt in voice_options_for(lang):
        if opt.engine == "edge":
            return opt.id
    return VOICES.get(lang, VOICES["en"])


def speak(text, lang="en", pitch=0, engine_instance=None, voice=None):
    """engine_instance: qual AudioEngine (qual dispositivo de saida) tocar o
    audio. Default None usa o engine global (minha fala). A fala recebida
    passa um engine proprio (core.singleton.received_tts_engine) pra poder
    usar um dispositivo de saida diferente — ver core/singleton.py.

    voice: ID de uma VoiceOption especifica (core/voices.py). None usa a voz
    padrao do idioma — sempre a mesma que o app ja usava antes desse
    parametro existir, entao quem nunca mexer na escolha de voz nao nota
    diferenca nenhuma. Se a voz resolvida for do motor local Kokoro
    (core/local_tts.py) mas ele nao estiver disponivel nessa maquina, cai
    automaticamente pra voz edge-tts padrao do idioma — nunca fica mudo."""
    text = _clean_text(text)
    if not text:
        print("❌ TTS vazio ignorado")
        return

    lang = normalize_lang_code(lang)
    opt = find_voice_option(lang, voice) or voice_options_for(lang)[0]
    target_engine = engine_instance or engine

    with tts_lock:
        tmp_path = None
        try:
            if opt.engine == "kokoro" and local_tts.KOKORO_AVAILABLE:
                try:
                    tmp_path = local_tts.generate(text, opt.id, opt.kokoro_lang)
                except Exception as e:
                    print("❌ Kokoro error, usando edge-tts:", e)
                    tmp_path = None

            if tmp_path is None:
                edge_voice = opt.id if opt.engine == "edge" else _default_edge_voice(lang)
                fd, tmp_path = tempfile.mkstemp(suffix=".mp3")
                os.close(fd)
                asyncio.run(_generate_edge(text, edge_voice, tmp_path, pitch))

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
