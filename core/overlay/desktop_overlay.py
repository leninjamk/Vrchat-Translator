"""
Overlay de desktop: janela Qt sem borda, sempre no topo, transparente a
cliques (nao rouba foco nem bloqueia controles), usada quando o overlay
dentro do headset (OpenVR) nao esta disponivel ou nao foi escolhido.
Mesma interface publica de core/overlay/openvr_overlay.py, pra o
OverlayManager poder trocar de backend sem mudar nada por fora.
"""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class DesktopOverlayWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.NoFocus)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._label = QLabel("")
        self._label.setWordWrap(True)
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setTextFormat(Qt.PlainText)
        layout.addWidget(self._label)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

        self.setMaximumWidth(720)
        self.resize(560, 120)

    def is_available(self) -> bool:
        return True

    def show_text(self, text, *, duration_seconds=6.0, always_visible=False,
                   font_size=20, opacity=0.9, scale=1.0, max_lines=4):
        self.setWindowOpacity(max(0.1, min(opacity, 1.0)))
        self._label.setStyleSheet(
            f"background-color: rgba(15, 15, 18, 235); color: white; "
            f"font-size: {max(int(font_size * scale), 8)}pt; font-weight: 600; "
            f"padding: 14px 20px; border-radius: 14px;"
        )

        lines = (text or "").splitlines() or [text or ""]
        if len(lines) > max_lines:
            lines = lines[-max_lines:]
        self._label.setText("\n".join(lines))

        self.adjustSize()
        self._position_bottom_center()
        self.show()
        self.raise_()

        self._hide_timer.stop()
        if not always_visible:
            self._hide_timer.start(int(max(duration_seconds, 0.5) * 1000))

    def _position_bottom_center(self, margin_bottom: int = 140):
        screen = self.screen() or QGuiApplication.primaryScreen()
        if not screen:
            return
        geo = screen.availableGeometry()
        x = geo.x() + (geo.width() - self.width()) // 2
        y = geo.y() + geo.height() - self.height() - margin_bottom
        self.move(x, y)

    def set_always_visible(self, always_visible: bool, duration_seconds: float = 6.0):
        """Chamado quando o usuario alterna 'Sempre visivel' pelo switch —
        sem isso, um texto ja exibido com always_visible=True nunca
        comecava a contar pra sumir ate a PROXIMA fala chegar (show_text
        e o unico lugar que arma o timer)."""
        if always_visible:
            self._hide_timer.stop()
        elif not self._hide_timer.isActive():
            self._hide_timer.start(int(max(duration_seconds, 0.5) * 1000))

    def hide_now(self):
        self._hide_timer.stop()
        self.hide()

    def shutdown(self):
        self._hide_timer.stop()
        self.close()
