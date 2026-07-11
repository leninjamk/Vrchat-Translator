"""
Protecao contra eco: enquanto o TTS local esta tocando (e por uma curta janela
de carencia depois), o reconhecimento do audio recebido (loopback) e pausado,
pra nao reconhecer a propria voz traduzida como se fosse outra pessoa falando.
"""
import threading
import time


class EchoGuard:
    def __init__(self, grace_period: float = 0.7):
        self.grace_period = grace_period
        self.enabled = True
        self._lock = threading.Lock()
        self._tts_active = False
        self._release_at = 0.0

    def mark_tts_start(self):
        with self._lock:
            self._tts_active = True

    def mark_tts_end(self):
        with self._lock:
            self._tts_active = False
            self._release_at = time.monotonic() + self.grace_period

    def should_block(self) -> bool:
        if not self.enabled:
            return False
        with self._lock:
            if self._tts_active:
                return True
            return time.monotonic() < self._release_at


echo_guard = EchoGuard()
