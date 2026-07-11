"""
SpeakerRecognitionService: captura o audio que esta SAINDO por um dispositivo
de reproducao (loopback WASAPI via PyAudioWPatch), segmenta a fala por
deteccao de silencio (VAD por energia), e reaproveita o MESMO reconhecedor
(speech_recognition + Google) e o MESMO tradutor (core/translate) que ja sao
usados para o meu proprio microfone — so a origem do audio muda.

Este servico e completamente independente do MicRecognitionService (a leitura
do microfone continua em core/speech_to_text.py, intocada). Cada resultado
carrega um dicionario com "source": "received" para nunca ser confundido com
a minha propria fala.
"""
import queue
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, List, Optional, Tuple

import langdetect
import numpy as np
import pyaudiowpatch as pyaudio
import speech_recognition as sr

from core.audio_device_manager import LoopbackDevice, PYAUDIO_LOCK
from core.echo_guard import echo_guard
from core.speaker_audio_source import SpeakerAudioSource
from core.translate import translate

RECOGNIZER_SAMPLE_RATE = 16000
SAMPLE_WIDTH_BYTES = 2  # int16

# langdetect usa um gerador pseudo-aleatorio internamente e sem uma seed fixa
# o mesmo texto pode ocasionalmente detectar linguas diferentes entre chamadas.
langdetect.DetectorFactory.seed = 0


def _normalize_lang_code(code: str) -> str:
    """'pt-BR' -> 'pt', 'zh-TW' -> 'zh' — langdetect so retorna o codigo base
    (ISO 639-1), entao comparamos so essa parte pra decidir se bateu."""
    return (code or "").split("-")[0].lower()


def _text_matches_language(text: str, expected_code: str) -> bool:
    """Confere se o TEXTO reconhecido realmente parece estar escrito na
    lingua que foi pedida ao Google — e o que permite tentar varias linguas
    candidatas e descartar reconhecimentos que so "pareciam certos" por causa
    de pronuncia/sotaque parecido."""
    try:
        detected = langdetect.detect(text)
    except Exception:
        return False
    return _normalize_lang_code(detected) == _normalize_lang_code(expected_code)


@dataclass
class ReceivedSpeechResult:
    source: str
    original_text: str
    translated_text: str
    source_language: str
    target_language: str
    timestamp: str


def _stereo_to_mono(raw_bytes: bytes, channels: int) -> bytes:
    if channels <= 1 or not raw_bytes:
        return raw_bytes
    arr = np.frombuffer(raw_bytes, dtype=np.int16)
    usable = (len(arr) // channels) * channels
    if usable <= 0:
        return b""
    arr = arr[:usable].reshape(-1, channels)
    mono = arr.mean(axis=1).astype(np.int16)
    return mono.tobytes()


def _rms(raw_mono_bytes: bytes) -> float:
    if not raw_mono_bytes:
        return 0.0
    arr = np.frombuffer(raw_mono_bytes, dtype=np.int16).astype(np.float64)
    if arr.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(arr ** 2)))


def _resample_mono_int16(raw_bytes: bytes, src_rate: int, dst_rate: int):
    """Resample simples por interpolacao linear (numpy), suficiente para fala."""
    if src_rate == dst_rate or not raw_bytes:
        return raw_bytes, src_rate
    arr = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32)
    if arr.size < 2:
        return raw_bytes, src_rate
    duration = len(arr) / src_rate
    dst_len = max(int(duration * dst_rate), 1)
    src_idx = np.arange(len(arr))
    dst_idx = np.linspace(0, len(arr) - 1, num=dst_len)
    resampled = np.interp(dst_idx, src_idx, arr).astype(np.int16)
    return resampled.tobytes(), dst_rate


class SpeakerRecognitionService:
    """Um servico = um fluxo (audio recebido -> texto -> traducao). Independente
    do reconhecimento do microfone."""

    def __init__(self):
        self.recognizer = sr.Recognizer()

        self._source: Optional[SpeakerAudioSource] = None
        self._raw_queue: "queue.Queue[bytes]" = queue.Queue()
        self._segment_queue: "queue.Queue[tuple]" = queue.Queue(maxsize=5)
        self._vad_thread: Optional[threading.Thread] = None
        self._process_thread: Optional[threading.Thread] = None
        self._running = False
        self._recent_texts = {}

        # Configuracao de VAD/segmentacao (todos ajustaveis pela UI)
        self.energy_threshold = 400.0
        self.min_speech_duration = 0.3
        self.silence_duration_to_end = 0.8
        self.max_segment_duration = 15.0
        self.queue_max_size = 5

        # Idiomas candidatos da fala recebida (definidos manualmente na UI —
        # marque uma ou mais). Com 1 candidato so, reconhece direto nela.
        # Com 2+, tenta cada uma e usa a primeira cujo TEXTO reconhecido bate
        # com a lingua pedida (via langdetect); se nenhuma bater com confianca,
        # fica com o texto mais longo entre as tentativas (heuristica).
        self.candidate_languages: List[str] = ["pt"]
        self.target_language = "pt"
        self.last_test_matched_language: Optional[str] = None

        # Callbacks (thread-safe do lado de quem os consome — normalmente a UI
        # conecta um Qt Signal aqui em vez de mexer em widgets diretamente)
        self.on_speech_started: Optional[Callable[[], None]] = None
        self.on_speech_ended: Optional[Callable[[], None]] = None
        self.on_transcription_ready: Optional[Callable[[str], None]] = None
        self.on_translation_ready: Optional[Callable[[ReceivedSpeechResult], None]] = None
        self.on_error: Optional[Callable[[str, bool], None]] = None  # (mensagem, fatal)
        self.on_level_changed: Optional[Callable[[float], None]] = None
        self.on_test_result: Optional[Callable[[Optional[str], Optional[str]], None]] = None
        self.on_source_status: Optional[Callable[[str], None]] = None  # mensagens informativas da fonte de audio

    @staticmethod
    def _safe_call(fn, *args):
        if fn is not None:
            try:
                fn(*args)
            except Exception:
                pass

    def is_running(self) -> bool:
        return self._running

    # ── captura continua ─────────────────────────────────────────────────

    def start(self, source: SpeakerAudioSource) -> bool:
        """source: de onde vem o audio (dispositivo inteiro ou um app
        especifico — ver core/speaker_audio_source.py). O resto do pipeline
        (VAD, reconhecimento, traducao, dedup) nao muda em nada — so recebe
        blocos de PCM cru atraves de on_audio, sem saber de onde vieram."""
        if self._running:
            return False

        self._segment_queue = queue.Queue(maxsize=max(self.queue_max_size, 1))
        self._raw_queue = queue.Queue()  # fresco a cada start (evita sobra de uma sessao anterior)

        self._running = True
        ok = source.start(
            on_audio=self._on_source_audio,
            on_error=lambda msg, fatal: self._safe_call(self.on_error, msg, fatal),
            on_status=lambda msg: self._safe_call(self.on_source_status, msg),
            on_ready=self._on_source_ready,
        )
        if not ok:
            self._running = False
            return False

        self._source = source
        self._process_thread = threading.Thread(target=self._process_loop, daemon=True)
        self._process_thread.start()
        return True

    def _on_source_audio(self, raw_bytes: bytes):
        if self._running:
            self._raw_queue.put(raw_bytes)

    def _on_source_ready(self, sample_rate: int, channels: int, frames_per_buffer: int):
        """Chamado (de qualquer thread) quando a fonte sabe o formato real do
        audio — so entao da pra iniciar o VAD. No modo 'aplicativo
        especifico' isso pode demorar (esperando o app abrir); ate la o
        _process_thread ja esta de pe, so ocioso (a fila de segmentos
        continua vazia)."""
        if self._vad_thread is not None and self._vad_thread.is_alive():
            return
        self._vad_thread = threading.Thread(
            target=self._vad_loop, args=(sample_rate, channels, frames_per_buffer), daemon=True,
        )
        self._vad_thread.start()

    def stop(self):
        self._running = False
        if self._source is not None:
            try:
                self._source.stop()
            except Exception:
                pass
            self._source = None
        self._drain(self._raw_queue)

    @staticmethod
    def _drain(q: "queue.Queue"):
        while not q.empty():
            try:
                q.get_nowait()
            except queue.Empty:
                break

    def _vad_loop(self, sample_rate, channels, frames_per_buffer):
        speaking = False
        segment_chunks = []
        speech_duration = 0.0
        silence_duration = 0.0
        chunk_duration = frames_per_buffer / sample_rate
        last_level_emit = 0.0

        while self._running:
            try:
                raw = self._raw_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            mono = _stereo_to_mono(raw, channels)

            if echo_guard.should_block():
                if speaking:
                    speaking = False
                    segment_chunks = []
                    speech_duration = 0.0
                    silence_duration = 0.0
                    self._safe_call(self.on_speech_ended)
                continue

            energy = _rms(mono)
            now = time.monotonic()
            if now - last_level_emit > 0.1:
                self._safe_call(self.on_level_changed, min(energy / 32768.0, 1.0))
                last_level_emit = now

            is_loud = energy >= self.energy_threshold

            if not speaking:
                if is_loud:
                    speaking = True
                    segment_chunks = [mono]
                    speech_duration = chunk_duration
                    silence_duration = 0.0
                    self._safe_call(self.on_speech_started)
                continue

            segment_chunks.append(mono)
            speech_duration += chunk_duration
            silence_duration = 0.0 if is_loud else silence_duration + chunk_duration

            finished_by_silence = silence_duration >= self.silence_duration_to_end
            finished_by_maxlen = speech_duration >= self.max_segment_duration
            if not (finished_by_silence or finished_by_maxlen):
                continue

            speaking = False
            total_duration = speech_duration
            pcm = b"".join(segment_chunks)
            segment_chunks = []
            speech_duration = 0.0
            silence_duration = 0.0
            self._safe_call(self.on_speech_ended)

            if total_duration >= self.min_speech_duration:
                self._enqueue_segment(pcm, sample_rate)

    def _enqueue_segment(self, pcm_mono_bytes: bytes, sample_rate: int):
        try:
            self._segment_queue.put_nowait((pcm_mono_bytes, sample_rate))
            return
        except queue.Full:
            pass
        try:
            self._segment_queue.get_nowait()
        except queue.Empty:
            pass
        self._safe_call(self.on_error, "Fila de reconhecimento cheia — descartando o segmento mais antigo.", False)
        try:
            self._segment_queue.put_nowait((pcm_mono_bytes, sample_rate))
        except queue.Full:
            pass

    def _process_loop(self):
        while self._running or not self._segment_queue.empty():
            try:
                pcm_mono_bytes, sample_rate = self._segment_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            self._process_segment(pcm_mono_bytes, sample_rate)

    def _recognize_best(self, audio_data) -> Tuple[Optional[str], Optional[str]]:
        """Tenta reconhecer o audio em cada lingua candidata (na ordem em que
        foram marcadas na UI) e devolve (texto, codigo_da_lingua_vencedora).
        (None, None) se nenhuma candidata reconheceu nada."""
        candidates = self.candidate_languages or ["en"]

        attempts: List[Tuple[str, str]] = []
        for code in candidates:
            try:
                text = self.recognizer.recognize_google(audio_data, language=code).strip()
            except sr.UnknownValueError:
                continue
            if text:
                attempts.append((text, code))
            if len(candidates) == 1:
                break

        if not attempts:
            return None, None
        if len(attempts) == 1:
            return attempts[0]

        for text, code in attempts:
            if _text_matches_language(text, code):
                return text, code

        # nenhuma bateu com confianca — fica com o texto mais longo (heuristica:
        # reconhecimento na lingua errada tende a sair mais curto/truncado)
        return max(attempts, key=lambda t: len(t[0]))

    def _process_segment(self, pcm_mono_bytes: bytes, sample_rate: int):
        try:
            resampled, out_rate = _resample_mono_int16(pcm_mono_bytes, sample_rate, RECOGNIZER_SAMPLE_RATE)
            audio_data = sr.AudioData(resampled, out_rate, SAMPLE_WIDTH_BYTES)
            text, matched_language = self._recognize_best(audio_data)
        except Exception as e:
            self._safe_call(self.on_error, f"Falha no reconhecimento da fala recebida: {e}", False)
            return

        if not text:
            return

        if self._is_recent_duplicate(text):
            return

        self._safe_call(self.on_transcription_ready, text)

        try:
            translated = translate(text, self.target_language, source=matched_language)
        except Exception as e:
            self._safe_call(self.on_error, f"Falha ao traduzir a fala recebida: {e}", False)
            return

        result = ReceivedSpeechResult(
            source="received",
            original_text=text,
            translated_text=translated,
            source_language=matched_language,
            target_language=self.target_language,
            timestamp=datetime.now().strftime("%H:%M:%S"),
        )
        self._safe_call(self.on_translation_ready, result)

    def _is_recent_duplicate(self, text: str, window_seconds: float = 5.0) -> bool:
        now = time.monotonic()
        norm = " ".join(text.lower().split())
        self._recent_texts = {k: v for k, v in self._recent_texts.items() if now - v < window_seconds * 2}
        last_seen = self._recent_texts.get(norm)
        self._recent_texts[norm] = now
        return last_seen is not None and (now - last_seen) < window_seconds

    # ── modo de teste (nivel + uma transcricao curta, sem tocar nada) ──────

    def run_test(self, device: LoopbackDevice, duration: float = 4.0):
        threading.Thread(target=self._test_worker, args=(device, duration), daemon=True).start()

    def _test_worker(self, device: LoopbackDevice, duration: float):
        chunks = []
        level_queue: "queue.Queue[bytes]" = queue.Queue()

        # so o abrir/fechar do stream precisa do lock global do PyAudio; o
        # loop de leitura abaixo so mexe numa Queue local, entao roda solto.
        with PYAUDIO_LOCK:
            pa = pyaudio.PyAudio()
            try:
                dev_info = pa.get_device_info_by_index(device.index)
                sample_rate = int(dev_info["defaultSampleRate"])
                channels = int(dev_info.get("maxInputChannels", 2)) or 2
                frames_per_buffer = max(int(sample_rate * 0.03), 256)

                def _callback(in_data, frame_count, time_info, status):
                    level_queue.put(in_data)
                    return (None, pyaudio.paContinue)

                stream = pa.open(
                    format=pyaudio.paInt16, channels=channels, rate=sample_rate,
                    frames_per_buffer=frames_per_buffer, input=True,
                    input_device_index=device.index, stream_callback=_callback,
                )
                stream.start_stream()
            except Exception as e:
                pa.terminate()
                self._safe_call(self.on_test_result, None, str(e))
                return

        try:
            t0 = time.monotonic()
            while time.monotonic() - t0 < duration:
                try:
                    raw = level_queue.get(timeout=0.2)
                except queue.Empty:
                    continue
                mono = _stereo_to_mono(raw, channels)
                chunks.append(mono)
                self._safe_call(self.on_level_changed, min(_rms(mono) / 32768.0, 1.0))
        finally:
            with PYAUDIO_LOCK:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception:
                    pass
                try:
                    pa.terminate()
                except Exception:
                    pass

        pcm = b"".join(chunks)
        if not pcm:
            self._safe_call(self.on_test_result, None, "Nenhum áudio capturado nesse dispositivo.")
            return
        try:
            resampled, out_rate = _resample_mono_int16(pcm, sample_rate, RECOGNIZER_SAMPLE_RATE)
            audio_data = sr.AudioData(resampled, out_rate, SAMPLE_WIDTH_BYTES)
            text, matched_language = self._recognize_best(audio_data)
            self.last_test_matched_language = matched_language
            self._safe_call(self.on_test_result, text or "", None)
        except Exception as e:
            self._safe_call(self.on_test_result, None, str(e))
