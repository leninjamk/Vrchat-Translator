"""
Componentes visuais reutilizaveis da UI (tema escuro, cantos arredondados).

O ModernCombo NAO abre um popup em uma janela de SO separada (ao contrario do
QComboBox nativo / do antigo VRCombobox do Tkinter). O dropdown e um QFrame
filho da propria janela principal, posicionado manualmente. Isso e essencial
para overlays de VR (SteamVR/Quest Link): eles capturam a superficie composta
de UMA janela, e uma janela de popup nativa separada nao entra nessa captura.
Como filho da mesma janela, o dropdown sempre aparece corretamente no overlay.
"""
from PySide6.QtCore import Qt, Signal, Property, QEvent, QPoint, QRect, QRectF, QSize, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPainter, QColor
from PySide6.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QFrame,
    QScrollArea, QSizePolicy,
)

ACCENT = "#4C8BF5"
ACCENT_HOVER = "#3D74D6"
ACCENT_SOFT = "#1B2C4D"
RECEIVED_ACCENT = "#9B7BF0"
RECEIVED_SOFT = "#241B3F"
BG = "#121212"
CARD_BG = "#1C1C1E"
BORDER = "#2A2A2C"
SURFACE = "#232325"
SURFACE_HOVER = "#2A2A2C"
TEXT = "#F2F2F2"
TEXT_MUTED = "#8A8A8E"
TEXT_SECONDARY = "#B8B8BD"
DANGER = "#E5484D"
DANGER_HOVER = "#C93E42"
SUCCESS = "#30D158"
WARNING = "#FFA500"

STATUS_LISTENING = "listening"
STATUS_PAUSED = "paused"
STATUS_STOPPED = "stopped"
STATUS_ERROR = "error"
STATUS_DISCONNECTED = "disconnected"

STATUS_STATES = {
    STATUS_LISTENING: ("Escutando...", ACCENT),
    STATUS_PAUSED: ("Pausado", WARNING),
    STATUS_STOPPED: ("Parado", TEXT_MUTED),
    STATUS_ERROR: ("Erro de áudio", DANGER),
    STATUS_DISCONNECTED: ("Sem conexão", DANGER),
}

STYLESHEET = f"""
QWidget {{
    background-color: {BG};
    color: {TEXT};
    font-family: 'Segoe UI';
    font-size: 10pt;
}}
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}

#Card {{
    background-color: {CARD_BG};
    border: 1px solid {BORDER};
    border-radius: 14px;
}}
#CardTitle {{
    color: {TEXT_MUTED};
    font-size: 9pt;
    font-weight: 600;
    letter-spacing: 1px;
    background: transparent;
}}
#RowLabel {{ color: {TEXT}; font-size: 10pt; background: transparent; }}
#RowHint {{ color: {TEXT_MUTED}; font-size: 8pt; background: transparent; }}

#ComboBox {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 10px;
}}
#ComboBox:hover {{ border: 1px solid {ACCENT}; }}
#ComboBox:focus {{ border: 1px solid {ACCENT}; }}
#ComboBoxDisabled {{
    background-color: #1A1A1B;
    border: 1px solid {BORDER};
    border-radius: 10px;
}}
#ComboLabel {{ color: {TEXT}; background: transparent; }}
#ComboLabelDisabled {{ color: #4A4A4C; background: transparent; }}
#ComboChevron {{ color: {TEXT_MUTED}; background: transparent; }}

#ComboPopup {{
    background-color: #1E1E1F;
    border: 1px solid {ACCENT};
    border-radius: 12px;
}}
QPushButton#ComboRow {{
    text-align: left;
    background: transparent;
    border: none;
    border-radius: 8px;
    padding: 8px 10px;
    color: {TEXT};
}}
QPushButton#ComboRow:hover {{ background-color: {SURFACE_HOVER}; color: {ACCENT}; }}
QPushButton#ComboRow:pressed {{ background-color: {ACCENT_SOFT}; color: {ACCENT}; }}

QPushButton#Ghost {{
    background-color: transparent;
    border: 1px solid {BORDER};
    border-radius: 10px;
    color: {TEXT_MUTED};
    padding: 8px;
    font-weight: 600;
}}
QPushButton#Ghost:hover {{ border-color: {ACCENT}; color: {ACCENT}; }}
QPushButton#Ghost:pressed {{ background-color: {ACCENT_SOFT}; }}
QPushButton#Ghost:disabled {{ color: #4A4A4C; border-color: {BORDER}; }}
QPushButton#Ghost:focus {{ border-color: {ACCENT}; }}

QPushButton#GhostAccent {{
    background-color: {RECEIVED_SOFT};
    border: 2px solid {RECEIVED_ACCENT};
    border-radius: 20px;
    color: {RECEIVED_ACCENT};
    padding: 10px;
    font-weight: 700;
    font-size: 10.5pt;
}}
QPushButton#GhostAccent:hover {{ background-color: {RECEIVED_ACCENT}; color: white; }}
QPushButton#GhostAccent:pressed {{ background-color: {RECEIVED_ACCENT}; color: white; }}
QPushButton#GhostAccent:checked {{ background-color: {RECEIVED_ACCENT}; color: white; }}

QPushButton#GhostBlue {{
    background-color: {ACCENT_SOFT};
    border: 1px solid {ACCENT};
    border-radius: 14px;
    color: {ACCENT};
    padding: 9px;
    font-weight: 700;
}}
QPushButton#GhostBlue:hover {{ background-color: {ACCENT}; color: white; }}
QPushButton#GhostBlue:pressed {{ background-color: {ACCENT_HOVER}; color: white; }}

QPushButton#IconGhost {{
    background-color: transparent;
    border: 1px solid {BORDER};
    border-radius: 8px;
    color: {TEXT_MUTED};
    padding: 4px 8px;
    font-weight: 600;
}}
QPushButton#IconGhost:hover {{ border-color: {ACCENT}; color: {ACCENT}; }}
QPushButton#IconGhost:pressed {{ background-color: {ACCENT_SOFT}; }}
QPushButton#IconGhost:checked {{ background-color: {ACCENT_SOFT}; border-color: {ACCENT}; color: {ACCENT}; }}

QPushButton#FilterChip {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 12px;
    color: {TEXT_MUTED};
    padding: 4px 12px;
    font-size: 8pt;
    font-weight: 700;
}}
QPushButton#FilterChip:hover {{ border-color: {ACCENT}; color: {ACCENT}; }}
QPushButton#FilterChip:checked {{ background-color: {ACCENT}; border-color: {ACCENT}; color: white; }}

QLineEdit#SearchField {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 9px;
    padding: 6px 10px;
    color: {TEXT};
}}
QLineEdit#SearchField:focus {{ border-color: {ACCENT}; }}

QToolTip {{
    background-color: #26262A;
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 4px 8px;
    border-radius: 6px;
}}

QSlider::groove:horizontal {{
    background: {SURFACE};
    height: 6px;
    border-radius: 3px;
}}
QSlider::sub-page:horizontal {{
    background: {ACCENT};
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    background: #FFFFFF;
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
}}

#Log {{
    background-color: #141415;
    border: 1px solid {BORDER};
    border-radius: 12px;
    padding: 6px;
}}

#MessageBlock {{
    background-color: #1A1A1C;
    border: 1px solid {BORDER};
    border-left: 3px solid {BORDER};
    border-radius: 10px;
}}
#MessageBlock[category="translated"] {{ border-left: 3px solid {ACCENT}; }}
#MessageBlock[category="same_lang"] {{ border-left: 3px solid {ACCENT}; }}
#MessageBlock[category="received"] {{ border-left: 3px solid {RECEIVED_ACCENT}; }}
#MessageBlock[category="error"] {{ border-left: 3px solid {DANGER}; }}
#MessageBlock[category="warning"] {{ border-left: 3px solid {WARNING}; }}

#LastTranslation {{
    background-color: {ACCENT_SOFT};
    border: 1px solid {ACCENT};
    border-radius: 12px;
}}
#LastReceived {{
    background-color: {RECEIVED_SOFT};
    border: 1px solid {RECEIVED_ACCENT};
    border-radius: 12px;
}}

QCheckBox#LangCheck {{
    color: {TEXT_SECONDARY};
    background: transparent;
    spacing: 8px;
    padding: 3px 2px;
}}
QCheckBox#LangCheck:hover {{ color: {TEXT}; }}
QCheckBox#LangCheck::indicator {{
    width: 15px;
    height: 15px;
    border: 1px solid {BORDER};
    border-radius: 4px;
    background-color: {SURFACE};
}}
QCheckBox#LangCheck::indicator:hover {{ border-color: {ACCENT}; }}
QCheckBox#LangCheck::indicator:checked {{
    background-color: {ACCENT};
    border-color: {ACCENT};
}}

QScrollBar:vertical {{
    background: transparent;
    width: 9px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: #3A3A3C; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
"""

PRIMARY_BTN_QSS = f"""
QPushButton {{
    background-color: {ACCENT};
    border: 2px solid transparent;
    border-radius: 20px;
    color: white;
    font-weight: 700;
    font-size: 11pt;
    padding: 12px;
}}
QPushButton:hover {{ background-color: {ACCENT_HOVER}; }}
QPushButton:pressed {{ background-color: #33619E; }}
QPushButton:focus {{ border: 2px solid #8AB2F8; }}
QPushButton:disabled {{ background-color: #33415C; color: #8A93A3; }}
"""

DANGER_BTN_QSS = f"""
QPushButton {{
    background-color: {DANGER};
    border: 2px solid transparent;
    border-radius: 20px;
    color: white;
    font-weight: 700;
    font-size: 11pt;
    padding: 12px;
}}
QPushButton:hover {{ background-color: {DANGER_HOVER}; }}
QPushButton:pressed {{ background-color: #9C3134; }}
QPushButton:focus {{ border: 2px solid #F0A5A7; }}
QPushButton:disabled {{ background-color: #4A2A2B; color: #8A7273; }}
"""


def make_card(title: str):
    """Cria um QFrame arredondado com titulo, retorna (frame, content_layout)."""
    frame = QFrame()
    frame.setObjectName("Card")
    outer = QVBoxLayout(frame)
    outer.setContentsMargins(14, 4, 14, 4)
    outer.setSpacing(3)

    lbl = QLabel(title.upper())
    lbl.setObjectName("CardTitle")
    outer.addWidget(lbl)

    content = QVBoxLayout()
    content.setSpacing(3)
    outer.addLayout(content)
    return frame, content


class ToggleSwitch(QWidget):
    """Switch estilo iOS, com animacao suave."""

    toggled = Signal(bool)

    def __init__(self, checked: bool = False, parent=None):
        super().__init__(parent)
        self.setFixedSize(44, 24)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self._checked = checked
        self._pos = 1.0 if checked else 0.0
        self._enabled = True

        self._anim = QPropertyAnimation(self, b"knobPos", self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.InOutCubic)

    def _get_pos(self):
        return self._pos

    def _set_pos(self, v):
        self._pos = v
        self.update()

    knobPos = Property(float, _get_pos, _set_pos)

    def isChecked(self):
        return self._checked

    def setChecked(self, val: bool, animate: bool = True):
        val = bool(val)
        if val == self._checked and not animate:
            return
        self._checked = val
        end = 1.0 if val else 0.0
        if animate:
            self._anim.stop()
            self._anim.setStartValue(self._pos)
            self._anim.setEndValue(end)
            self._anim.start()
        else:
            self._pos = end
            self.update()

    def set_enabled_visual(self, enabled: bool):
        self._enabled = enabled
        self.setCursor(Qt.PointingHandCursor if enabled else Qt.ArrowCursor)
        self.update()

    def mousePressEvent(self, e):
        if self._enabled:
            self.setChecked(not self._checked)
            self.toggled.emit(self._checked)

    def keyPressEvent(self, e):
        if self._enabled and e.key() in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter):
            self.setChecked(not self._checked)
            self.toggled.emit(self._checked)
        else:
            super().keyPressEvent(e)

    @staticmethod
    def _lerp(c1: QColor, c2: QColor, t: float) -> QColor:
        return QColor(
            int(c1.red() + (c2.red() - c1.red()) * t),
            int(c1.green() + (c2.green() - c1.green()) * t),
            int(c1.blue() + (c2.blue() - c1.blue()) * t),
        )

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        off = QColor("#3A3A3C") if self._enabled else QColor("#262627")
        on = QColor(ACCENT) if self._enabled else QColor("#3A5A8F")
        track = self._lerp(off, on, self._pos)

        p.setPen(Qt.NoPen)
        p.setBrush(track)
        r = self.height() / 2
        p.drawRoundedRect(0, 0, self.width(), self.height(), r, r)

        knob_d = self.height() - 4
        x = 2 + self._pos * (self.width() - knob_d - 4)
        p.setBrush(QColor("#FFFFFF") if self._enabled else QColor("#8A8A8E"))
        p.drawEllipse(QRectF(x, 2, knob_d, knob_d))

        if self.hasFocus():
            p.setPen(QColor(ACCENT))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(1, 1, self.width() - 2, self.height() - 2, r, r)


class LevelMeter(QWidget):
    """Barra horizontal simples pro medidor de nivel do teste de audio recebido."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(8)
        self._level = 0.0

    def set_level(self, level: float):
        self._level = max(0.0, min(level, 1.0))
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(SURFACE))
        p.drawRoundedRect(0, 0, self.width(), self.height(), 4, 4)

        w = int(self.width() * self._level)
        if w > 0:
            if self._level < 0.55:
                color = QColor(SUCCESS)
            elif self._level < 0.85:
                color = QColor(WARNING)
            else:
                color = QColor(DANGER)
            p.setBrush(color)
            p.drawRoundedRect(0, 0, w, self.height(), 4, 4)


class StatusIndicator(QWidget):
    """Ponto colorido + texto de estado, reutilizado no cabecalho principal e no painel de conversa."""

    def __init__(self, initial_state: str = STATUS_STOPPED, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._dot = QLabel()
        self._dot.setFixedSize(10, 10)
        self._label = QLabel()
        self._label.setObjectName("RowHint")
        layout.addWidget(self._dot)
        layout.addWidget(self._label)

        text, color = STATUS_STATES[initial_state]
        self.set_status(text, color)

    def set_status(self, text: str, color: str):
        self._label.setText(text)
        self._label.setStyleSheet(f"color: {color}; font-size: 9pt; font-weight: 600; background: transparent;")
        self._dot.setStyleSheet(f"background-color: {color}; border-radius: 5px;")

    def set_state(self, state_key: str):
        text, color = STATUS_STATES[state_key]
        self.set_status(text, color)


class ModernCombo(QWidget):
    """Combobox custom com cantos arredondados; popup e widget-filho (VR-safe)."""

    currentTextChanged = Signal(str)

    def __init__(self, window: QWidget, values=None, parent=None):
        super().__init__(parent)
        self._window = window
        self._values = list(values or [])
        self._index = 0
        self._popup = None
        self._enabled = True
        self._full_text = ""

        self.setFixedHeight(27)
        self.setObjectName("ComboBox")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 12, 0)
        self._label = QLabel()
        self._label.setObjectName("ComboLabel")
        self._chevron = QLabel("⌄")
        self._chevron.setObjectName("ComboChevron")
        layout.addWidget(self._label, 1)
        layout.addWidget(self._chevron, 0)

        if self._values:
            self._set_label_text(self._values[0])

        self._window.installEventFilter(self)

    def sizeHint(self):
        return QSize(220, 27)

    def minimumSizeHint(self):
        return QSize(60, 27)

    # ---- API compativel com uso simples ----------------------------------

    def _set_label_text(self, text: str):
        self._full_text = text
        self.setToolTip(text)
        avail = self._label.width() or max(self.width() - 40, 60)
        elided = self._label.fontMetrics().elidedText(text, Qt.ElideRight, avail)
        self._label.setText(elided)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self._full_text:
            self._set_label_text(self._full_text)

    def set_values(self, values, keep_selection=False):
        current = self.currentText() if keep_selection else None
        self._values = list(values)
        self._index = 0
        if current in self._values:
            self._index = self._values.index(current)
        self._set_label_text(self._values[self._index] if self._values else "")

    def currentText(self) -> str:
        if not self._values:
            return ""
        return self._values[self._index]

    def setCurrentText(self, text: str):
        if text in self._values:
            self._index = self._values.index(text)
            self._set_label_text(text)

    def setCurrentIndex(self, idx: int):
        if 0 <= idx < len(self._values):
            self._index = idx
            self._set_label_text(self._values[idx])

    def set_enabled(self, enabled: bool):
        self._enabled = enabled
        self.setCursor(Qt.PointingHandCursor if enabled else Qt.ArrowCursor)
        self.setObjectName("ComboBox" if enabled else "ComboBoxDisabled")
        self._label.setObjectName("ComboLabel" if enabled else "ComboLabelDisabled")
        self.setFocusPolicy(Qt.StrongFocus if enabled else Qt.NoFocus)
        self._refresh_style(self)
        self._refresh_style(self._label)
        if not enabled:
            self._close_popup()

    def keyPressEvent(self, e):
        if not self._enabled:
            return
        if e.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space, Qt.Key_Down):
            self._toggle_popup()
        elif e.key() == Qt.Key_Escape:
            self._close_popup()
        else:
            super().keyPressEvent(e)

    @staticmethod
    def _refresh_style(widget):
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    # ---- Popup --------------------------------------------------------------

    def mousePressEvent(self, e):
        if self._enabled:
            self._toggle_popup()

    def _toggle_popup(self):
        if self._popup is not None:
            self._close_popup()
        else:
            self._open_popup()

    def _open_popup(self):
        if not self._values:
            return

        popup = QFrame(self._window)
        popup.setObjectName("ComboPopup")
        popup.setAttribute(Qt.WA_StyledBackground, True)
        vlay = QVBoxLayout(popup)
        vlay.setContentsMargins(4, 4, 4, 4)

        scroll = QScrollArea(popup)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        inner = QWidget()
        inner_lay = QVBoxLayout(inner)
        inner_lay.setContentsMargins(0, 0, 0, 0)
        inner_lay.setSpacing(1)

        for i, v in enumerate(self._values):
            row = QPushButton(v)
            row.setObjectName("ComboRow")
            row.setCursor(Qt.PointingHandCursor)
            row.clicked.connect(lambda checked=False, idx=i: self._select(idx))
            inner_lay.addWidget(row)
        inner_lay.addStretch(1)

        scroll.setWidget(inner)
        vlay.addWidget(scroll)

        top_left = self.mapTo(self._window, QPoint(0, self.height() + 4))
        row_h = 34
        wanted_h = min(280, row_h * len(self._values) + 12)
        available_h = self._window.height() - top_left.y() - 12
        h = max(min(wanted_h, available_h), 50)

        popup.setGeometry(top_left.x(), top_left.y(), self.width(), int(h))
        popup.show()
        popup.raise_()
        self._popup = popup

    def _select(self, idx):
        self._index = idx
        self._label.setText(self._values[idx])
        self._close_popup()
        self.currentTextChanged.emit(self._values[idx])

    def _close_popup(self):
        if self._popup is not None:
            self._popup.deleteLater()
            self._popup = None

    def eventFilter(self, obj, event):
        if self._popup is not None and event.type() == QEvent.MouseButtonPress:
            gpos = event.globalPosition().toPoint()
            local = self._window.mapFromGlobal(gpos)
            popup_rect = self._popup.geometry()
            trigger_rect = QRect(self.mapTo(self._window, QPoint(0, 0)), self.size())
            if not popup_rect.contains(local) and not trigger_rect.contains(local):
                self._close_popup()
        return False
