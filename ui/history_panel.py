"""
Painel de conversa: cada reconhecimento vira um bloco (nao um texto corrido).
Toda escrita na UI passa por HistoryPanel.add_entry(), que emite um Qt Signal
(seguro entre threads) antes de tocar em qualquer widget.

Dois tipos de bloco, sempre visualmente diferenciados (borda esquerda colorida
+ rotulo), nunca misturados:
  - minha fala (local)     -> rotulo "VOCE",     borda azul
  - fala recebida (loopback) -> rotulo "RECEBIDO", borda roxa
"""
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QFrame,
    QScrollArea, QLineEdit, QSizePolicy, QFileDialog, QApplication,
)

from core.history import (
    HistoryEntry, HistoryStore,
    CATEGORY_TRANSLATED, CATEGORY_SAME_LANG, CATEGORY_ERROR, CATEGORY_WARNING, CATEGORY_RECEIVED,
    FILTER_ALL, FILTER_MINE, FILTER_RECEIVED, FILTER_ERRORS, FILTER_CATEGORIES,
)
from ui.widgets import (
    ACCENT, TEXT, TEXT_MUTED, TEXT_SECONDARY, DANGER, WARNING, RECEIVED_ACCENT,
    StatusIndicator, STATUS_STOPPED,
)

MAX_HISTORY_ENTRIES = 500
LOCAL_CATEGORIES = (CATEGORY_TRANSLATED, CATEGORY_SAME_LANG)


class MessageBlock(QFrame):
    """Um bloco = um reconhecimento (cabecalho + original + traducao)."""

    def __init__(self, entry: HistoryEntry, show_confidence: bool = False, on_replay=None, parent=None):
        super().__init__(parent)
        self.entry = entry
        self.setObjectName("MessageBlock")
        self.setProperty("category", entry.category)
        self.setAttribute(Qt.WA_StyledBackground, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        layout.addLayout(self._build_header(entry, on_replay))

        if entry.category in (CATEGORY_ERROR, CATEGORY_WARNING):
            color = DANGER if entry.category == CATEGORY_ERROR else WARNING
            msg = QLabel(entry.original)
            msg.setTextFormat(Qt.PlainText)
            msg.setWordWrap(True)
            msg.setStyleSheet(f"color: {color}; font-size: 10pt; background: transparent;")
            layout.addWidget(msg)
            return

        original = QLabel(entry.original)
        original.setTextFormat(Qt.PlainText)
        original.setWordWrap(True)
        original.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 10pt; background: transparent;")
        layout.addWidget(original)

        if entry.category == CATEGORY_SAME_LANG:
            info = QLabel("Mesmo idioma — sem tradução")
            info.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 9pt; font-style: italic; background: transparent;")
            layout.addWidget(info)
        elif entry.translated:
            translated = QLabel(entry.translated)
            translated.setTextFormat(Qt.PlainText)
            translated.setWordWrap(True)
            translated.setStyleSheet(f"color: {TEXT}; font-size: 10pt; font-weight: 600; background: transparent;")
            layout.addWidget(translated)

        if show_confidence and entry.category == CATEGORY_RECEIVED and entry.confidence is not None:
            conf = QLabel(f"Confiança: {entry.confidence * 100:.0f}%")
            conf.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 8pt; background: transparent;")
            layout.addWidget(conf)

        status_bits = []
        if entry.category in LOCAL_CATEGORIES:
            if entry.sent_to_chatbox:
                status_bits.append("💬 Enviado ao VRChat")
            if entry.tts_played:
                status_bits.append("🔊 Voz reproduzida")
        if status_bits:
            status_lbl = QLabel("   ·   ".join(status_bits))
            status_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 8pt; background: transparent;")
            layout.addWidget(status_lbl)

    def _build_header(self, entry: HistoryEntry, on_replay):
        row = QHBoxLayout()
        row.setSpacing(6)

        parts = [entry.speaker.upper()]
        if entry.source_language:
            parts.append(entry.source_language.upper())
        parts.append(entry.timestamp)
        header_color = RECEIVED_ACCENT if entry.category == CATEGORY_RECEIVED else ACCENT
        if entry.category in (CATEGORY_ERROR, CATEGORY_WARNING):
            header_color = DANGER if entry.category == CATEGORY_ERROR else WARNING

        head = QLabel("  ·  ".join(parts))
        head.setStyleSheet(
            f"color: {header_color}; font-size: 8pt; font-weight: 700; "
            f"letter-spacing: 1px; background: transparent;"
        )
        row.addWidget(head)
        row.addStretch(1)

        if entry.category not in (CATEGORY_ERROR, CATEGORY_WARNING):
            copy_orig_btn = QPushButton("📋")
            copy_orig_btn.setObjectName("IconGhost")
            copy_orig_btn.setCursor(Qt.PointingHandCursor)
            copy_orig_btn.setToolTip("Copiar texto original")
            copy_orig_btn.clicked.connect(lambda: QApplication.clipboard().setText(entry.original))
            row.addWidget(copy_orig_btn)

            if entry.translated:
                copy_tr_btn = QPushButton("📄")
                copy_tr_btn.setObjectName("IconGhost")
                copy_tr_btn.setCursor(Qt.PointingHandCursor)
                copy_tr_btn.setToolTip("Copiar tradução")
                copy_tr_btn.clicked.connect(lambda: QApplication.clipboard().setText(entry.translated))
                row.addWidget(copy_tr_btn)

            if entry.category in LOCAL_CATEGORIES and on_replay is not None:
                replay_btn = QPushButton("🔊")
                replay_btn.setObjectName("IconGhost")
                replay_btn.setCursor(Qt.PointingHandCursor)
                replay_btn.setToolTip("Reproduzir esta tradução novamente")
                replay_btn.clicked.connect(lambda: on_replay(entry))
                row.addWidget(replay_btn)

        return row


class HistoryPanel(QFrame):
    """Painel direito completo: cabecalho, ultimas mensagens em destaque,
    filtros, blocos e rodape."""

    closeRequested = Signal()
    replayEntryRequested = Signal(object)
    entryReceived = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.store = HistoryStore(max_entries=MAX_HISTORY_ENTRIES)
        self._blocks = []
        self._active_filter = FILTER_ALL
        self._search_query = ""
        self._autoscroll = True
        self.show_confidence = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 14, 18, 14)
        outer.setSpacing(10)

        outer.addLayout(self._build_header())
        outer.addLayout(self._build_filter_row())
        outer.addWidget(self._build_blocks_area(), 1)
        outer.addLayout(self._build_footer())

        self.entryReceived.connect(self._on_entry_received)

    # ── construcao ───────────────────────────────────────────────────────

    def _build_header(self):
        row = QHBoxLayout()
        title = QLabel("CONVERSA EM TEMPO REAL")
        title.setObjectName("CardTitle")
        row.addWidget(title)

        self.status_indicator = StatusIndicator(STATUS_STOPPED)
        row.addWidget(self.status_indicator)
        row.addStretch(1)

        search_btn = QPushButton("🔍")
        search_btn.setObjectName("IconGhost")
        search_btn.setCursor(Qt.PointingHandCursor)
        search_btn.setToolTip("Focar no campo de busca do histórico")
        search_btn.clicked.connect(lambda: self._search_field.setFocus())
        row.addWidget(search_btn)

        clear_btn = QPushButton("🧹 Limpar")
        clear_btn.setObjectName("Ghost")
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.setToolTip("Limpar todo o histórico local (Ctrl+K)")
        clear_btn.clicked.connect(self.clear)
        row.addWidget(clear_btn)

        close_btn = QPushButton("✕")
        close_btn.setObjectName("IconGhost")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setToolTip("Fechar painel de conversa (Esc)")
        close_btn.clicked.connect(self.closeRequested.emit)
        row.addWidget(close_btn)

        return row

    def _build_filter_row(self):
        row = QHBoxLayout()
        row.addLayout(self._build_filters())

        self._search_field = QLineEdit()
        self._search_field.setObjectName("SearchField")
        self._search_field.setPlaceholderText("Buscar no histórico...")
        self._search_field.setFixedWidth(180)
        self._search_field.setToolTip("Filtra os blocos pelo texto original ou traduzido")
        self._search_field.textChanged.connect(self._on_search_changed)
        row.addWidget(self._search_field)
        return row

    def _build_filters(self):
        row = QHBoxLayout()
        self._filter_buttons = {}
        options = [
            (FILTER_ALL, "Tudo"),
            (FILTER_MINE, "Minha fala"),
            (FILTER_RECEIVED, "Recebido"),
            (FILTER_ERRORS, "Erros"),
        ]
        for key, label in options:
            btn = QPushButton(label)
            btn.setObjectName("FilterChip")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, k=key: self._set_filter(k))
            row.addWidget(btn)
            self._filter_buttons[key] = btn
        self._filter_buttons[FILTER_ALL].setChecked(True)
        row.addStretch(1)
        return row

    def _build_blocks_area(self):
        scroll = QScrollArea()
        scroll.setObjectName("Log")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        container = QWidget()
        self._blocks_layout = QVBoxLayout(container)
        self._blocks_layout.setContentsMargins(8, 8, 8, 8)
        self._blocks_layout.setSpacing(6)
        self._blocks_layout.addStretch(1)

        scroll.setWidget(container)
        self._scroll_area = scroll
        return scroll

    def _build_footer(self):
        row = QHBoxLayout()
        self._autoscroll_btn = QPushButton("⏸ Pausar rolagem")
        self._autoscroll_btn.setObjectName("Ghost")
        self._autoscroll_btn.setCheckable(True)
        self._autoscroll_btn.setCursor(Qt.PointingHandCursor)
        self._autoscroll_btn.setToolTip("Pausar a rolagem automática para ler mensagens antigas")
        self._autoscroll_btn.toggled.connect(self._on_autoscroll_toggle)
        row.addWidget(self._autoscroll_btn)

        row.addStretch(1)

        self._count_label = QLabel("0 mensagens")
        self._count_label.setObjectName("RowHint")
        row.addWidget(self._count_label)

        export_btn = QPushButton("⬇ Exportar TXT")
        export_btn.setObjectName("Ghost")
        export_btn.setCursor(Qt.PointingHandCursor)
        export_btn.setToolTip("Exportar todo o histórico para um arquivo .txt")
        export_btn.clicked.connect(self._export_txt)
        row.addWidget(export_btn)
        return row

    # ── API publica ──────────────────────────────────────────────────────

    def add_entry(self, entry: HistoryEntry):
        """Chamado a partir de QUALQUER thread; emite um signal (thread-safe)."""
        self.entryReceived.emit(entry)

    def set_status(self, text: str, color: str):
        self.status_indicator.set_status(text, color)

    def set_state(self, state_key: str):
        self.status_indicator.set_state(state_key)

    def set_show_confidence(self, show: bool):
        self.show_confidence = show

    def clear(self):
        self.store.clear()
        for b in self._blocks:
            self._blocks_layout.removeWidget(b)
            b.hide()
            b.deleteLater()
        self._blocks.clear()
        self._count_label.setText("0 mensagens")

    # ── internos ─────────────────────────────────────────────────────────

    def _on_entry_received(self, entry: HistoryEntry):
        overflow = self.store.add(entry)
        for _ in range(overflow):
            if self._blocks:
                old = self._blocks.pop(0)
                self._blocks_layout.removeWidget(old)
                old.hide()
                old.deleteLater()

        block = MessageBlock(
            entry, show_confidence=self.show_confidence,
            on_replay=lambda e: self.replayEntryRequested.emit(e),
        )
        self._blocks.append(block)
        self._blocks_layout.insertWidget(self._blocks_layout.count() - 1, block)
        self._apply_filter_to_block(block)

        self._count_label.setText(f"{len(self._blocks)} mensagens")

        if self._autoscroll:
            QTimer.singleShot(0, self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        bar = self._scroll_area.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _set_filter(self, key):
        self._active_filter = key
        for k, btn in self._filter_buttons.items():
            btn.setChecked(k == key)
        self._reapply_filters()

    def _on_search_changed(self, text):
        self._search_query = text.strip().lower()
        self._reapply_filters()

    def _reapply_filters(self):
        for block in self._blocks:
            self._apply_filter_to_block(block)

    def _apply_filter_to_block(self, block: MessageBlock):
        entry = block.entry
        allowed = FILTER_CATEGORIES.get(self._active_filter)
        visible = allowed is None or entry.category in allowed
        if visible and self._search_query:
            q = self._search_query
            visible = q in entry.original.lower() or q in (entry.translated or "").lower()
        block.setVisible(visible)

    def _on_autoscroll_toggle(self, paused):
        self._autoscroll = not paused
        self._autoscroll_btn.setText("▶ Retomar rolagem" if paused else "⏸ Pausar rolagem")

    def _export_txt(self):
        if not self.store.list_entries():
            return
        path, _ = QFileDialog.getSaveFileName(self, "Exportar histórico", "conversa.txt", "Texto (*.txt)")
        if path:
            try:
                self.store.export_txt(path)
                self.set_status("Histórico exportado!", ACCENT)
            except OSError as e:
                self.set_status(f"Erro ao exportar: {e}", DANGER)
