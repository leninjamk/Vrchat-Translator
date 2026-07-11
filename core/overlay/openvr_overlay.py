"""
Overlay real dentro do headset via OpenVR/SteamVR.

Padrao de uso do SDK (init em modo Background, createOverlay, setOverlayRaw
pra textura, setOverlayTransformTrackedDeviceRelative pra ancorar na HMD)
baseado na abordagem comprovada do VRCT (misyaguziya/VRCT, MIT) — a ideia foi
reaproveitada, mas todo o codigo abaixo foi escrito do zero para este projeto
(estrutura mais simples: um unico overlay de texto, sem multiplos tamanhos).

So funciona com o SteamVR aberto. Se nao estiver, is_available() retorna
False e o OverlayManager cai pro overlay de desktop automaticamente.
"""
import ctypes
import threading
import time
from typing import Optional

import openvr
from PIL import Image, ImageDraw, ImageFont

OVERLAY_KEY = "vrchat_translator.received_speech"
OVERLAY_NAME = "VRChat Translator - Fala Recebida"

IMG_WIDTH = 1400
IMG_HEIGHT = 360


def _hud_transform(y_offset: float = -0.35, z_distance: float = 1.3):
    """Matriz 3x4 relativa a HMD: parada um pouco abaixo do centro da visao,
    a alguns metros de distancia, sem rotacao (encarando o usuario)."""
    m = openvr.HmdMatrix34_t()
    rows = (
        (1.0, 0.0, 0.0, 0.0),
        (0.0, 1.0, 0.0, y_offset),
        (0.0, 0.0, 1.0, -abs(z_distance)),
    )
    for i in range(3):
        for j in range(4):
            m[i][j] = rows[i][j]
    return m


def _load_font(size: int):
    for candidate in ("segoeui.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(candidate, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _render_text_image(text: str, font_size: int) -> Image.Image:
    img = Image.new("RGBA", (IMG_WIDTH, IMG_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle(
        [8, 8, IMG_WIDTH - 8, IMG_HEIGHT - 8], radius=28, fill=(12, 12, 16, 235),
    )

    font = _load_font(font_size)
    lines = text.splitlines() or [text]

    line_height = font_size + 10
    total_h = len(lines) * line_height
    y = (IMG_HEIGHT - total_h) // 2
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        x = (IMG_WIDTH - w) // 2
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))
        y += line_height

    return img


class OpenVROverlayBackend:
    def __init__(self):
        self._lock = threading.Lock()
        self._vr_system = None
        self._overlay = None
        self._handle: Optional[int] = None
        self._initialized = False
        self._init_error: Optional[str] = None
        self._hide_timer: Optional[threading.Timer] = None

    # ── ciclo de vida ────────────────────────────────────────────────────

    def initialize(self) -> bool:
        with self._lock:
            if self._initialized:
                return True
            try:
                self._vr_system = openvr.init(openvr.VRApplication_Background)
                self._overlay = openvr.IVROverlay()
                self._handle = self._overlay.createOverlay(OVERLAY_KEY, OVERLAY_NAME)
                self._overlay.setOverlayWidthInMeters(self._handle, 1.0)
                self._overlay.setOverlayInputMethod(self._handle, openvr.VROverlayInputMethod_None)
                self._overlay.setOverlayTransformTrackedDeviceRelative(
                    self._handle, openvr.k_unTrackedDeviceIndex_Hmd, _hud_transform(),
                )
                self._initialized = True
                self._init_error = None
                return True
            except Exception as e:
                self._init_error = str(e)
                self._teardown_locked()
                return False

    def is_available(self) -> bool:
        if self._initialized and self._steamvr_still_running():
            return True
        return self.initialize()

    def _steamvr_still_running(self) -> bool:
        try:
            event = openvr.VREvent_t()
            while self._vr_system.pollNextEvent(event):
                if event.eventType == openvr.VREvent_Quit:
                    self._teardown_locked()
                    return False
            return True
        except Exception:
            self._teardown_locked()
            return False

    def last_error(self) -> Optional[str]:
        return self._init_error

    # ── exibicao (mesma interface do DesktopOverlayWindow) ─────────────────

    def show_text(self, text, *, duration_seconds=6.0, always_visible=False,
                   font_size=32, opacity=0.9, scale=1.0, max_lines=4):
        if not self.is_available():
            return

        lines = (text or "").splitlines() or [text or ""]
        if len(lines) > max_lines:
            lines = lines[-max_lines:]

        img = _render_text_image("\n".join(lines), font_size=int(font_size * 1.7))
        data = img.tobytes()
        buf = (ctypes.c_char * len(data)).from_buffer_copy(data)

        try:
            self._overlay.setOverlayWidthInMeters(self._handle, max(0.3, scale))
            self._overlay.setOverlayAlpha(self._handle, max(0.05, min(opacity, 1.0)))
            self._overlay.setOverlayRaw(self._handle, buf, img.width, img.height, 4)
            self._overlay.showOverlay(self._handle)
        except Exception as e:
            self._init_error = str(e)
            self._teardown_locked()
            return

        self._reset_hide_timer(duration_seconds, always_visible)

    def _reset_hide_timer(self, duration_seconds, always_visible):
        if self._hide_timer is not None:
            self._hide_timer.cancel()
            self._hide_timer = None
        if not always_visible:
            self._hide_timer = threading.Timer(max(duration_seconds, 0.5), self.hide_now)
            self._hide_timer.daemon = True
            self._hide_timer.start()

    def set_always_visible(self, always_visible: bool, duration_seconds: float = 6.0):
        """Mesma logica do backend de desktop: reage ao switch na hora,
        em vez de esperar a proxima fala pra comecar a contar o tempo."""
        if always_visible:
            if self._hide_timer is not None:
                self._hide_timer.cancel()
                self._hide_timer = None
        elif self._hide_timer is None:
            self._hide_timer = threading.Timer(max(duration_seconds, 0.5), self.hide_now)
            self._hide_timer.daemon = True
            self._hide_timer.start()

    def hide_now(self):
        if self._hide_timer is not None:
            self._hide_timer.cancel()
            self._hide_timer = None
        if self._initialized and self._handle is not None:
            try:
                self._overlay.hideOverlay(self._handle)
            except Exception:
                pass

    def shutdown(self):
        self.hide_now()
        with self._lock:
            self._teardown_locked()

    def _teardown_locked(self):
        if self._initialized:
            try:
                if self._handle is not None:
                    self._overlay.destroyOverlay(self._handle)
            except Exception:
                pass
            try:
                openvr.shutdown()
            except Exception:
                pass
        self._initialized = False
        self._vr_system = None
        self._overlay = None
        self._handle = None
