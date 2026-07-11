"""
Ponto unico de contato entre a aplicacao e o overlay (desktop OU OpenVR).
Trocar de backend (ou o backend falhar/SteamVR fechar) nao exige mudar nada
fora deste arquivo.
"""
from typing import Optional


class OverlayManager:
    def __init__(self):
        self.enabled = False
        self.backend_name = "desktop"  # "desktop" | "openvr"

        self.duration_seconds = 6.0
        self.always_visible = False
        self.font_size = 20
        self.opacity = 0.9
        self.scale = 1.0
        self.max_lines = 4

        self._desktop_backend = None
        self._openvr_backend = None
        self._active_backend = None

    def set_desktop_backend(self, backend):
        self._desktop_backend = backend
        if self.backend_name == "desktop":
            self._active_backend = backend

    def set_openvr_backend(self, backend):
        self._openvr_backend = backend

    def openvr_available(self) -> bool:
        return self._openvr_backend is not None and self._openvr_backend.is_available()

    def select_backend(self, name: str) -> bool:
        """Troca o backend ativo. Retorna False se o backend pedido nao
        estiver disponivel (ex.: "openvr" sem SteamVR rodando)."""
        if name == "openvr":
            if not self.openvr_available():
                return False
            self._active_backend = self._openvr_backend
        else:
            self._active_backend = self._desktop_backend
        self.backend_name = name
        return True

    def show_text(self, text: str):
        if not self.enabled or self._active_backend is None or not text:
            return
        try:
            self._active_backend.show_text(
                text,
                duration_seconds=self.duration_seconds,
                always_visible=self.always_visible,
                font_size=self.font_size,
                opacity=self.opacity,
                scale=self.scale,
                max_lines=self.max_lines,
            )
        except Exception:
            pass

    def set_always_visible(self, checked: bool):
        self.always_visible = checked
        if self._active_backend is not None:
            try:
                self._active_backend.set_always_visible(checked, self.duration_seconds)
            except Exception:
                pass

    def hide(self):
        if self._active_backend is not None:
            try:
                self._active_backend.hide_now()
            except Exception:
                pass

    def shutdown(self):
        for backend in (self._desktop_backend, self._openvr_backend):
            if backend is not None:
                try:
                    backend.shutdown()
                except Exception:
                    pass


overlay_manager = OverlayManager()
