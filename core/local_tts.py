"""
Wrapper isolado do motor de voz LOCAL Kokoro-82M (github.com/hexgrad/kokoro),
opcional e 100% gratuito — roda no proprio PC, sem internet, sem chave de
API. Ver core/voices.py pra saber quais idiomas/vozes usam esse motor (so 8
dos 17 idiomas do app tem cobertura Kokoro).

TUDO que importa 'kokoro' fica neste arquivo de proposito: se o pacote nao
estiver instalado, se a versao de Python nao bater (Kokoro exige 3.10 a
<3.13), ou se o espeak-ng (instalador separado do Windows, nao e pacote
Python) nao estiver disponivel, KOKORO_AVAILABLE fica False e o resto do
app nem fica sabendo que esse motor existe — core/tts.py cai automaticamente
pra voz edge-tts padrao daquele idioma. Nunca deve derrubar o app.
"""
import os
import shutil
import tempfile
import threading

import numpy as np

_ESPEAK_AVAILABLE = shutil.which("espeak-ng") is not None

KOKORO_AVAILABLE = False
UNAVAILABLE_REASON = None

if not _ESPEAK_AVAILABLE:
    UNAVAILABLE_REASON = "espeak-ng não encontrado no PATH"
else:
    try:
        from kokoro import KPipeline
        import soundfile as sf
        KOKORO_AVAILABLE = True
    except Exception as e:
        KPipeline = None
        sf = None
        UNAVAILABLE_REASON = str(e)

_SAMPLE_RATE = 24000
_pipelines = {}
_pipelines_lock = threading.Lock()


def _get_pipeline(kokoro_lang: str):
    with _pipelines_lock:
        pipeline = _pipelines.get(kokoro_lang)
        if pipeline is None:
            pipeline = KPipeline(lang_code=kokoro_lang)
            _pipelines[kokoro_lang] = pipeline
        return pipeline


def generate(text: str, voice_id: str, kokoro_lang: str) -> str:
    """Gera audio com uma voz Kokoro e devolve o caminho de um .wav
    temporario (o chamador e responsavel por apagar depois, igual ja faz
    com o .mp3 do edge-tts em core/tts.py). Lanca excecao se o motor nao
    estiver disponivel ou a geracao falhar — o chamador trata isso caindo
    pro edge-tts, nunca deixa o usuario sem voz nenhuma."""
    if not KOKORO_AVAILABLE:
        raise RuntimeError(f"Kokoro não disponível: {UNAVAILABLE_REASON}")

    pipeline = _get_pipeline(kokoro_lang)

    chunks = [audio for _gs, _ps, audio in pipeline(text, voice=voice_id)]
    if not chunks:
        raise RuntimeError("Kokoro não gerou áudio (texto vazio ou voz inválida)")
    full_audio = chunks[0] if len(chunks) == 1 else np.concatenate(chunks)

    fd, tmp_path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    sf.write(tmp_path, full_audio, _SAMPLE_RATE)
    return tmp_path
