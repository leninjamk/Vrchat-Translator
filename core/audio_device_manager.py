"""
Enumeracao de dispositivos de "audio recebido" (loopback WASAPI) e deteccao de
troca/remocao de dispositivo por polling leve.

O microfone e a saida do TTS continuam enumerados via sounddevice diretamente
em ui/app.py (nao alterado) — este modulo cuida SO da terceira categoria nova:
o loopback que escuta o que esta saindo pelos alto-falantes/fone (ou seja, o
que o VRChat esta reproduzindo).
"""
import threading
import time
from dataclasses import dataclass
from typing import Callable, List, Optional

import pyaudiowpatch as pyaudio

# PyAudioWPatch/PortAudio NAO e thread-safe para construir/enumerar PyAudio()
# de duas threads ao mesmo tempo — isso derruba o processo inteiro com um
# segmentation fault (native crash, sem excecao Python pra capturar). Todo
# lugar do projeto que cria um PyAudio(), enumera dispositivos ou abre/fecha
# um stream (aqui e em core/speaker_loopback.py) usa ESTE MESMO lock.
PYAUDIO_LOCK = threading.RLock()


@dataclass
class LoopbackDevice:
    index: int
    name: str
    sample_rate: int
    channels: int


def list_loopback_devices() -> List[LoopbackDevice]:
    """Lista os dispositivos de reproducao capturaveis via WASAPI loopback."""
    devices: List[LoopbackDevice] = []
    seen = set()
    with PYAUDIO_LOCK:
        p = pyaudio.PyAudio()
        try:
            for dev in p.get_loopback_device_info_generator():
                name = dev["name"]
                if name in seen:
                    continue
                seen.add(name)
                devices.append(LoopbackDevice(
                    index=dev["index"],
                    name=name,
                    sample_rate=int(dev["defaultSampleRate"]),
                    channels=int(dev["maxInputChannels"]) or 2,
                ))
        except Exception:
            pass
        finally:
            p.terminate()
    return devices


def get_default_loopback_device() -> Optional[LoopbackDevice]:
    """Loopback do dispositivo de reproducao PADRAO atual do Windows."""
    with PYAUDIO_LOCK:
        p = pyaudio.PyAudio()
        try:
            dev = p.get_default_wasapi_loopback()
            return LoopbackDevice(
                index=dev["index"],
                name=dev["name"],
                sample_rate=int(dev["defaultSampleRate"]),
                channels=int(dev["maxInputChannels"]) or 2,
            )
        except Exception:
            return None
        finally:
            p.terminate()


def find_loopback_device_by_name(name: str) -> Optional[LoopbackDevice]:
    for dev in list_loopback_devices():
        if dev.name == name:
            return dev
    return None


class LoopbackDeviceMonitor:
    """Compara a lista de dispositivos de loopback a cada `poll_interval`
    segundos e chama `on_change()` quando algo muda (troca, remocao, novo
    dispositivo). Nao usa COM/pycaw — e so uma comparacao periodica leve,
    entao a deteccao tem um atraso de no maximo `poll_interval` segundos."""

    def __init__(self, poll_interval: float = 3.0):
        self.poll_interval = poll_interval
        self.on_change: Optional[Callable[[], None]] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._last_names = set()

    def _snapshot(self):
        try:
            return {d.name for d in list_loopback_devices()}
        except Exception:
            return set()

    def _loop(self):
        self._last_names = self._snapshot()
        while self._running:
            time.sleep(self.poll_interval)
            if not self._running:
                break
            current = self._snapshot()
            if current != self._last_names:
                self._last_names = current
                if self.on_change:
                    try:
                        self.on_change()
                    except Exception:
                        pass

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
