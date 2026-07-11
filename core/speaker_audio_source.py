"""
Fontes de audio para o SpeakerRecognitionService (core/speaker_loopback.py).

O servico de reconhecimento so recebe blocos de PCM int16 crus atraves do
callback on_audio — ele nao sabe (nem precisa saber) de onde os bytes vem.
Isso permite trocar a fonte (dispositivo inteiro vs. um aplicativo especifico)
sem duplicar nada do pipeline de VAD/reconhecimento/traducao.

FullDeviceLoopbackSource: o comportamento que ja existia (loopback WASAPI do
dispositivo de reproducao inteiro via PyAudioWPatch), movido pra ca sem
nenhuma mudanca de comportamento.

ApplicationAudioSource: usa um processo auxiliar nativo (bin/app_loopback_
capture.exe) que fala a API de loopback POR PROCESSO do Windows
(AUDIOCLIENT_ACTIVATION_TYPE_PROCESS_LOOPBACK, Windows 10 2004+) — API sem
wrapper maduro em Python. O auxiliar escreve um cabecalho fixo de 16 bytes
(formato real negociado) e depois um fluxo continuo de PCM int16 na saida
padrao. Reconecta sozinho por nome de executavel se o app fechar/reabrir.
"""
import os
import struct
import subprocess
import threading
from abc import ABC, abstractmethod
from typing import Callable, Optional

import pyaudiowpatch as pyaudio

from core.audio_device_manager import LoopbackDevice, PYAUDIO_LOCK
from core.audio_sessions import find_pid_by_executable

HELPER_MAGIC = b"ALC1"
HELPER_HEADER_SIZE = 16
HELPER_HEADER_STRUCT = "<4sIHHHH"  # magic, sample_rate, channels, bits_per_sample, format_tag, reserved
RECONNECT_POLL_SECONDS = 2.0
HEADER_READ_TIMEOUT_SECONDS = 5.0
READER_CHUNK_BYTES = 4096


def default_helper_path() -> str:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, "bin", "app_loopback_capture.exe")


class SpeakerAudioSource(ABC):
    """sample_rate/channels/frames_per_buffer so ficam validos DEPOIS que
    on_ready() e chamado (uma unica vez por ciclo start()/stop())."""

    def __init__(self):
        self.sample_rate: int = 0
        self.channels: int = 0
        self.frames_per_buffer: int = 0

    @abstractmethod
    def start(self, on_audio: Callable[[bytes], None],
              on_error: Callable[[str, bool], None],
              on_status: Callable[[str], None],
              on_ready: Callable[[int, int, int], None]) -> bool:
        """on_audio(bytes): chamado de QUALQUER thread a cada bloco de PCM
        int16. on_ready(sample_rate, channels, frames_per_buffer): chamado
        UMA VEZ, quando o formato real e conhecido. on_status(msg): mensagens
        informativas (nao-erro). on_error(msg, fatal): falhas."""
        raise NotImplementedError

    @abstractmethod
    def stop(self) -> None:
        raise NotImplementedError


class FullDeviceLoopbackSource(SpeakerAudioSource):
    """Modo 'Todo o audio do computador' — comportamento inalterado."""

    def __init__(self, device: LoopbackDevice):
        super().__init__()
        self.device = device
        self._pa: Optional["pyaudio.PyAudio"] = None
        self._stream = None
        self._on_audio: Optional[Callable[[bytes], None]] = None

    def start(self, on_audio, on_error, on_status, on_ready) -> bool:
        self._on_audio = on_audio
        with PYAUDIO_LOCK:
            pa = pyaudio.PyAudio()
            try:
                dev_info = pa.get_device_info_by_index(self.device.index)
                sample_rate = int(dev_info["defaultSampleRate"])
                channels = int(dev_info.get("maxInputChannels", 2)) or 2
                frames_per_buffer = max(int(sample_rate * 0.03), 256)

                stream = pa.open(
                    format=pyaudio.paInt16,
                    channels=channels,
                    rate=sample_rate,
                    frames_per_buffer=frames_per_buffer,
                    input=True,
                    input_device_index=self.device.index,
                    stream_callback=self._make_audio_callback(),
                )
            except Exception as e:
                pa.terminate()
                on_error(f"Não foi possível abrir o dispositivo de áudio recebido: {e}", True)
                return False

        self._pa = pa
        self._stream = stream
        self.sample_rate = sample_rate
        self.channels = channels
        self.frames_per_buffer = frames_per_buffer
        stream.start_stream()
        on_ready(sample_rate, channels, frames_per_buffer)
        return True

    def _make_audio_callback(self):
        def _callback(in_data, frame_count, time_info, status):
            on_audio = self._on_audio
            if on_audio is not None:
                on_audio(in_data)
            return (None, pyaudio.paContinue)
        return _callback

    def stop(self) -> None:
        self._on_audio = None
        with PYAUDIO_LOCK:
            if self._stream is not None:
                try:
                    self._stream.stop_stream()
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None
            if self._pa is not None:
                try:
                    self._pa.terminate()
                except Exception:
                    pass
                self._pa = None


class ApplicationAudioSource(SpeakerAudioSource):
    """Modo 'Aplicativo específico'."""

    def __init__(self, executable_name: str, helper_path: Optional[str] = None):
        super().__init__()
        self.executable_name = executable_name
        self.helper_path = helper_path or default_helper_path()

        self._on_audio: Optional[Callable[[bytes], None]] = None
        self._on_error: Optional[Callable[[str, bool], None]] = None
        self._on_status: Optional[Callable[[str], None]] = None
        self._on_ready: Optional[Callable[[int, int, int], None]] = None

        self._proc: Optional[subprocess.Popen] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._watchdog_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._format_locked = False
        self._running = False

    def start(self, on_audio, on_error, on_status, on_ready) -> bool:
        if not os.path.isfile(self.helper_path):
            on_error(f"Componente de captura por aplicativo não encontrado: {self.helper_path}", True)
            return False

        self._on_audio = on_audio
        self._on_error = on_error
        self._on_status = on_status
        self._on_ready = on_ready
        self._stop_event.clear()
        self._running = True

        self._watchdog_thread = threading.Thread(target=self._watchdog_loop, daemon=True)
        self._watchdog_thread.start()
        return True

    def stop(self) -> None:
        self._running = False
        self._stop_event.set()
        proc = self._proc
        if proc is not None:
            try:
                proc.terminate()
            except Exception:
                pass
        if self._reader_thread is not None and self._reader_thread.is_alive():
            try:
                self._reader_thread.join(timeout=3.0)
            except Exception:
                pass
        if self._watchdog_thread is not None and self._watchdog_thread.is_alive():
            try:
                self._watchdog_thread.join(timeout=3.0)
            except Exception:
                pass
        self._reader_thread = None
        self._watchdog_thread = None
        self._proc = None
        self._on_audio = None
        self._on_error = None
        self._on_status = None
        self._on_ready = None

    # ── thread vigia: alterna entre 'aguardando' e 'conectado' ─────────────

    def _watchdog_loop(self):
        self._safe(self._on_status, f"Aguardando {self.executable_name} ser aberto novamente...")
        while self._running and not self._stop_event.is_set():
            pid = find_pid_by_executable(self.executable_name)
            if pid is None:
                if self._stop_event.wait(RECONNECT_POLL_SECONDS):
                    break
                continue

            if not self._attach(pid):
                if not self._running:
                    break  # erro fatal, _attach ja avisou e desligou
                if self._stop_event.wait(RECONNECT_POLL_SECONDS):
                    break
                continue

            self._safe(self._on_status, f"Ouvindo somente {self.executable_name}")

            proc = self._proc
            while self._running and not self._stop_event.is_set() and proc is not None:
                try:
                    proc.wait(timeout=1.0)
                    break
                except subprocess.TimeoutExpired:
                    continue

            if self._reader_thread is not None:
                self._reader_thread.join(timeout=2.0)
                self._reader_thread = None
            self._proc = None

            if not self._running or self._stop_event.is_set():
                break

            self._safe(self._on_status, f"Aguardando {self.executable_name} ser aberto novamente...")

    def _attach(self, pid: int) -> bool:
        try:
            proc = subprocess.Popen(
                [self.helper_path, "--pid", str(pid)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except Exception as e:
            self._fatal(f"Falha ao iniciar o componente de captura: {e}")
            return False

        header = self._read_header(proc)
        if header is None:
            stderr_text = self._drain_stderr(proc)
            msg = f"Não foi possível capturar o áudio de {self.executable_name}"
            if stderr_text:
                msg += f": {stderr_text}"
            self._safe(self._on_error, msg, False)
            return False

        sample_rate, channels, bits_per_sample = header
        if bits_per_sample != 16:
            self._drain_stderr(proc)
            self._fatal("Formato de áudio inesperado do componente de captura.")
            return False

        if self._format_locked and (sample_rate, channels) != (self.sample_rate, self.channels):
            self._drain_stderr(proc)
            self._fatal("O formato de áudio mudou entre reconexões — não é possível continuar com segurança.")
            return False

        frames_per_buffer = max(int(sample_rate * 0.03), 256)

        self._proc = proc
        self._reader_thread = threading.Thread(
            target=self._reader_loop, args=(proc, channels, frames_per_buffer), daemon=True,
        )
        self._reader_thread.start()

        if not self._format_locked:
            self.sample_rate = sample_rate
            self.channels = channels
            self.frames_per_buffer = frames_per_buffer
            self._format_locked = True
            self._safe(self._on_ready, sample_rate, channels, frames_per_buffer)

        return True

    def _fatal(self, msg: str):
        self._running = False
        self._stop_event.set()
        self._safe(self._on_error, msg, True)

    def _read_header(self, proc: subprocess.Popen):
        result = {}

        def _do_read():
            try:
                result["data"] = proc.stdout.read(HELPER_HEADER_SIZE)
            except Exception:
                result["data"] = None

        t = threading.Thread(target=_do_read, daemon=True)
        t.start()
        t.join(timeout=HEADER_READ_TIMEOUT_SECONDS)
        if t.is_alive():
            return None  # ficou preso esperando o helper — tratado como falha
        data = result.get("data")
        if not data or len(data) < HELPER_HEADER_SIZE:
            return None
        try:
            magic, sample_rate, channels, bits_per_sample, _format_tag, _reserved = struct.unpack(
                HELPER_HEADER_STRUCT, data
            )
        except struct.error:
            return None
        if magic != HELPER_MAGIC or sample_rate <= 0 or channels <= 0:
            return None
        return sample_rate, channels, bits_per_sample

    def _drain_stderr(self, proc: subprocess.Popen) -> str:
        try:
            proc.terminate()
        except Exception:
            pass
        stderr_data = b""
        try:
            _, stderr_data = proc.communicate(timeout=1.0)
        except Exception:
            try:
                proc.kill()
                _, stderr_data = proc.communicate(timeout=1.0)
            except Exception:
                stderr_data = stderr_data or b""
        try:
            return (stderr_data or b"").decode("utf-8", errors="ignore").strip()
        except Exception:
            return ""

    def _reader_loop(self, proc: subprocess.Popen, channels: int, frames_per_buffer: int):
        chunk_bytes = frames_per_buffer * channels * 2  # int16 = 2 bytes/amostra
        buf = bytearray()
        stdout = proc.stdout
        try:
            while self._running and not self._stop_event.is_set():
                data = stdout.read(READER_CHUNK_BYTES)
                if not data:
                    break
                buf.extend(data)
                while len(buf) >= chunk_bytes:
                    chunk = bytes(buf[:chunk_bytes])
                    del buf[:chunk_bytes]
                    on_audio = self._on_audio
                    if on_audio is not None:
                        on_audio(chunk)
        except Exception:
            pass

    @staticmethod
    def _safe(fn, *args):
        if fn is not None:
            try:
                fn(*args)
            except Exception:
                pass
