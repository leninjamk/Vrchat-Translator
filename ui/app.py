import json
import os
import sys
import threading
import time

import sounddevice as sd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import Qt, QTimer, QPoint, Signal, QVariantAnimation, QEasingCurve
from PySide6.QtGui import QGuiApplication, QShortcut, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QSlider, QCheckBox, QGridLayout, QScrollArea, QFrame,
)

from core.singleton import engine, received_tts_engine
from core.languages import LANGS
from core.voices import voice_options_for, find_voice_option, normalize_lang_code
from core.history import (
    HistoryEntry, CATEGORY_TRANSLATED, CATEGORY_SAME_LANG, CATEGORY_ERROR, CATEGORY_RECEIVED,
    SOURCE_LOCAL, SOURCE_RECEIVED,
)
from core.audio_device_manager import list_loopback_devices, get_default_loopback_device, find_loopback_device_by_name, LoopbackDeviceMonitor
from core.speaker_loopback import SpeakerRecognitionService
from core.speaker_audio_source import FullDeviceLoopbackSource, ApplicationAudioSource
from core.audio_sessions import list_audio_session_apps
from core.vrchat_osc_receiver import VRChatOSCReceiver
from core.overlay.overlay_manager import overlay_manager
from core.overlay.desktop_overlay import DesktopOverlayWindow
from core.overlay.openvr_overlay import OpenVROverlayBackend
from ui.widgets import (
    STYLESHEET, PRIMARY_BTN_QSS, DANGER_BTN_QSS,
    ACCENT, DANGER, WARNING, RECEIVED_ACCENT, TEXT_MUTED,
    STATUS_STATES, STATUS_LISTENING, STATUS_STOPPED, STATUS_ERROR,
    make_card, ModernCombo, ToggleSwitch, StatusIndicator, LevelMeter,
)
from ui.history_panel import HistoryPanel

# Empacotado (PyInstaller): __file__ resolve pra dentro de _internal/, mas
# queremos o settings.json visivel ao lado do .exe principal — usa
# sys.executable nesse caso. Rodando a partir do codigo-fonte, continua
# relativo a este arquivo, igual sempre foi.
if getattr(sys, "frozen", False):
    _APP_ROOT = os.path.dirname(sys.executable)
else:
    _APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS_FILE = os.path.join(_APP_ROOT, "settings.json")

# O painel esquerdo (controles) tem largura FIXA sempre. A ALTURA da janela
# tambem e sempre a MESMA (calculada uma unica vez a partir do sizeHint do
# painel esquerdo em _finalize_initial_size()) — ela NUNCA muda em runtime.
# Os dois paineis extras (configuracoes da fala recebida, e a conversa) so
# mexem na LARGURA: a janela ancora a borda DIREITA e cresce/encolhe pra
# ESQUERDA conforme cada painel abre/fecha (ver _current_target_width()).
LEFT_PANEL_WIDTH = 360
SETTINGS_PANEL_WIDTH = 340
ROOT_MARGIN_H = 24
PANEL_SPACING = 16
COMPACT_WIDTH = LEFT_PANEL_WIDTH + ROOT_MARGIN_H * 2   # 408
EXPANDED_WIDTH = 1040
SETTINGS_WIDTH_DELTA = SETTINGS_PANEL_WIDTH + PANEL_SPACING
CONVERSATION_WIDTH_DELTA = EXPANDED_WIDTH - COMPACT_WIDTH
PANEL_ANIM_MS = 260

CHATBOX_MODE_OFF = "Não enviar"
CHATBOX_MODE_ORIGINAL = "Somente original"
CHATBOX_MODE_TRANSLATED = "Somente tradução"
CHATBOX_MODE_BOTH = "Original + tradução"
CHATBOX_MODES = [CHATBOX_MODE_OFF, CHATBOX_MODE_ORIGINAL, CHATBOX_MODE_TRANSLATED, CHATBOX_MODE_BOTH]

OVERLAY_BACKEND_DESKTOP = "Desktop (janela flutuante)"
OVERLAY_BACKEND_OPENVR = "SteamVR (dentro do headset)"
OVERLAY_BACKENDS = [OVERLAY_BACKEND_DESKTOP, OVERLAY_BACKEND_OPENVR]

# Idiomas candidatos pra fala recebida (todos exceto "Auto Detect" — esse so
# faz sentido pra traducao de texto ja reconhecido, o Google recognize_google
# nao tem um modo "automatico" de verdade, entao "tentar varias candidatas e
# conferir o texto reconhecido" e como a gente aproxima isso aqui).
RECEIVED_LANG_ITEMS = [(name, code) for name, code in LANGS.items() if code != "auto"]
CODE_TO_LANG_NAME = {code: name for name, code in RECEIVED_LANG_ITEMS}
DEFAULT_RECEIVED_LANGS = ["pt"]

RECEIVED_STATUS_STOPPED = ("Parado", TEXT_MUTED)
RECEIVED_STATUS_LISTENING = ("Ouvindo...", RECEIVED_ACCENT)
RECEIVED_STATUS_SPEECH = ("Fala detectada", RECEIVED_ACCENT)
RECEIVED_STATUS_TRANSLATING = ("Traduzindo...", RECEIVED_ACCENT)
RECEIVED_STATUS_ERROR = ("Erro", DANGER)

# Fonte do audio da fala recebida — "Ouvir Pessoas" continua a mesma funcao,
# só muda de ONDE ela captura (ver core/speaker_audio_source.py).
SOURCE_MODE_FULL_DEVICE = "Todo o áudio do computador"
SOURCE_MODE_APPLICATION = "Aplicativo específico"
SOURCE_MODES = [SOURCE_MODE_FULL_DEVICE, SOURCE_MODE_APPLICATION]
SOURCE_MODE_KEY_TO_DISPLAY = {
    "full_device": SOURCE_MODE_FULL_DEVICE,
    "application": SOURCE_MODE_APPLICATION,
}
SOURCE_MODE_DISPLAY_TO_KEY = {v: k for k, v in SOURCE_MODE_KEY_TO_DISPLAY.items()}
WAITING_APP_SUFFIX = " (aguardando abrir)"


def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_settings(settings):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4, ensure_ascii=False)
    except Exception:
        pass


def _same_device_name(name_a: str, name_b: str) -> bool:
    """Compara nomes de dispositivo tolerando truncamento (MME limita a ~31
    caracteres enquanto DirectSound/WASAPI expõem o nome completo do MESMO
    aparelho) — usado tanto na deduplicacao da lista quanto ao restaurar o
    dispositivo salvo em settings.json, pra nao perder a selecao so porque
    o Windows reenumerou o dispositivo com uma variante de nome diferente."""
    a, b = name_a.strip(), name_b.strip()
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    return len(shorter) >= 8 and longer.lower().startswith(shorter.lower())


class MainWindow(QWidget):
    status_signal = Signal(str, str)
    received_status_signal = Signal(str, str)
    received_translation_signal = Signal(object)
    level_signal = Signal(float)
    test_result_signal = Signal(object, object)
    mute_changed_signal = Signal(bool)
    device_change_signal = Signal()

    def __init__(self):
        super().__init__()
        self.running = False
        self.mic_index = None
        self._animating = False
        self._active_anim = None
        self._vrchat_muted = False
        # Rede de seguranca contra o Qt/Windows reposicionar/redimensionar a
        # janela sozinho durante a animacao de largura (ver moveEvent/
        # resizeEvent e _enforce_anim_geometry, usados por _animate_to_width).
        self._anim_expected_geometry = None
        self._correcting_geometry = False

        self.setWindowTitle("VRChat Speech Translator — By: LeNinjaMK")
        self.setStyleSheet(STYLESHEET)

        self.status_signal.connect(self._set_status)
        self.received_status_signal.connect(self._set_received_status)
        self.received_translation_signal.connect(self._handle_received_translation)
        self.level_signal.connect(self._on_level_changed)
        self.test_result_signal.connect(self._on_test_result)
        self.mute_changed_signal.connect(self._on_mute_changed)
        self.device_change_signal.connect(self._on_loopback_devices_changed)

        self._settings = load_settings()
        self.panel_open = bool(self._settings.get("panel_open", False))
        self.settings_open = bool(self._settings.get("settings_open", False))
        self._voice_overrides = dict(self._settings.get("voice_overrides", {}))
        self._voice_combo_maps = {"my": {}, "received": {}}

        self.speaker_service = SpeakerRecognitionService()
        self.speaker_service.on_speech_started = lambda: self.received_status_signal.emit(*RECEIVED_STATUS_SPEECH)
        self.speaker_service.on_speech_ended = lambda: self.received_status_signal.emit(*RECEIVED_STATUS_LISTENING)
        self.speaker_service.on_transcription_ready = lambda text: self.received_status_signal.emit(*RECEIVED_STATUS_TRANSLATING)
        self.speaker_service.on_translation_ready = lambda result: self.received_translation_signal.emit(result)
        self.speaker_service.on_error = lambda msg, fatal: self._on_speaker_error(msg, fatal)
        self.speaker_service.on_level_changed = lambda level: self.level_signal.emit(level)
        self.speaker_service.on_test_result = lambda text, err: self.test_result_signal.emit(text, err)
        self.speaker_service.on_source_status = self._on_source_status

        self.osc_receiver = VRChatOSCReceiver()
        self.osc_receiver.on_mute_changed = lambda muted: self.mute_changed_signal.emit(muted)
        self.osc_receiver.on_error = lambda msg: self.status_signal.emit(msg, WARNING)

        self.device_monitor = LoopbackDeviceMonitor(poll_interval=4.0)
        self.device_monitor.on_change = lambda: self.device_change_signal.emit()
        self.device_monitor.start()

        self.overlay_mgr = overlay_manager
        self.overlay_mgr.set_desktop_backend(DesktopOverlayWindow())
        self.overlay_mgr.set_openvr_backend(OpenVROverlayBackend())

        # engine separado pra TTS da fala RECEBIDA — precisa poder apontar pro
        # meu fone/headset real, diferente do "Saída do TTS" da minha propria
        # fala (que normalmente aponta pro VB-Cable, indo pro VRChat).
        self.received_tts_engine = received_tts_engine

        self._enumerate_audio_devices()
        self._build_ui()
        self._setup_shortcuts()
        self._finalize_initial_size()
        self._restore_window_position()
        self._current_pos = self.pos()

    # ── construcao da UI ─────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(ROOT_MARGIN_H, 9, ROOT_MARGIN_H, 9)
        root.setSpacing(8)

        root.addLayout(self._build_header())

        body = QHBoxLayout()
        body.setSpacing(PANEL_SPACING)

        # Ordem da esquerda pra direita: [config. da fala recebida] [controles
        # principais] [conversa]. A janela ancora a borda DIREITA — entao o
        # painel de configuracoes, sendo o primeiro (mais a esquerda), sempre
        # aparece "abrindo pra esquerda" sem deslocar os controles principais
        # nem a conversa (eles ficam exatamente onde estavam).
        self.settings_panel = self._build_settings_panel()
        self.settings_panel.setVisible(False)
        body.addWidget(self.settings_panel, 0)

        body.addWidget(self._build_left_panel(), 0)

        # self.received_voice_combo mora no painel de configuracoes (construido
        # ACIMA), mas depende do idioma "Origem" (self.from_lang), que so passa
        # a existir no painel esquerdo (construido logo acima tambem, mas
        # DEPOIS) — por isso essa ligacao fica aqui, depois que os dois ja
        # existem, em vez de dentro de _build_settings_panel().
        self._refresh_voice_combo("received", self.from_lang.currentText())
        self.from_lang.currentTextChanged.connect(lambda t: self._refresh_voice_combo("received", t))
        self.received_voice_combo.currentTextChanged.connect(lambda _t: self._on_voice_combo_changed("received"))

        self.history_panel = HistoryPanel()
        # comeca sempre oculto; _finalize_initial_size() decide o estado inicial
        # depois que a geometria compacta ja estiver assentada (evita reflow com o
        # painel direito "fantasma", sem largura, quando a janela abre ja expandida)
        self.history_panel.setVisible(False)
        self.history_panel.closeRequested.connect(self._close_conversation_panel)
        self.history_panel.replayEntryRequested.connect(self._replay_entry)
        body.addWidget(self.history_panel, 1)

        root.addLayout(body, 1)

    def _build_header(self):
        row = QHBoxLayout()
        row.setContentsMargins(0, 5, 0, 5)

        logo = QLabel("VR")
        logo.setFixedSize(44, 44)
        logo.setAlignment(Qt.AlignCenter)
        logo.setStyleSheet(
            f"background-color: {ACCENT}; border-radius: 12px; "
            f"color: white; font-weight: 800; font-size: 12pt;"
        )
        row.addWidget(logo)

        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        title_box.setContentsMargins(12, 0, 0, 0)
        title = QLabel("VRChat Speech Translator")
        title.setStyleSheet("font-size: 16pt; font-weight: 800; background: transparent;")
        subtitle = QLabel("By: LeNinjaMK")
        subtitle.setStyleSheet(f"color: {ACCENT}; font-size: 9pt; font-weight: 700; background: transparent;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        row.addLayout(title_box)

        row.addStretch(1)

        # O status global so aparece com a janela expandida (no modo compacto o
        # espaco e curto demais para caber ao lado do titulo sem espremer o texto;
        # o painel de conversa ja tem seu proprio indicador de estado).
        self.header_status = StatusIndicator(STATUS_STOPPED)
        self.header_status.setVisible(self.panel_open)
        row.addWidget(self.header_status)

        return row

    def _build_left_panel(self):
        # Container simples, SEM QScrollArea: a altura da janela e calculada a
        # partir do sizeHint real deste container (ver _finalize_initial_size),
        # entao nunca falta espaco e nunca aparece barra de rolagem.
        container = QWidget()
        container.setFixedWidth(LEFT_PANEL_WIDTH)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        layout.addWidget(self._build_audio_card())
        layout.addWidget(self._build_language_voice_card())
        layout.addWidget(self._build_features_card())
        layout.addLayout(self._build_action_buttons())

        self.left_container = container
        return container

    def _row_label(self, text):
        lbl = QLabel(text)
        lbl.setObjectName("RowLabel")
        return lbl

    @staticmethod
    def _initial_received_langs(settings):
        codes = settings.get("received_langs")
        if isinstance(codes, list) and codes:
            valid = [c for c in codes if c in CODE_TO_LANG_NAME]
            if valid:
                return valid
        # migracao de um settings.json antigo (received_lang = um unico nome de exibicao)
        legacy_name = settings.get("received_lang")
        if legacy_name in LANGS and LANGS[legacy_name] != "auto":
            return [LANGS[legacy_name]]
        return list(DEFAULT_RECEIVED_LANGS)

    def _build_received_lang_checklist(self, content, selected_codes):
        """Lista de checkboxes (2 colunas) pra marcar quais linguas tentar
        reconhecer na fala recebida. Fica dentro de uma altura fixa+scroll
        LOCAL (so essa lista, nao a janela toda) pra nunca fazer o painel de
        configuracoes crescer alem da altura fixa da janela, mesmo com as
        {n} linguas suportadas todas visiveis na lista.""".format(n=len(RECEIVED_LANG_ITEMS))
        scroll = QScrollArea()
        scroll.setObjectName("LangChecklist")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFixedHeight(128)

        inner = QWidget()
        grid = QGridLayout(inner)
        grid.setContentsMargins(2, 2, 2, 2)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(2)

        self.received_lang_checks = {}
        cols = 2
        for i, (name, code) in enumerate(RECEIVED_LANG_ITEMS):
            cb = QCheckBox(name)
            cb.setObjectName("LangCheck")
            cb.setCursor(Qt.PointingHandCursor)
            cb.setChecked(code in selected_codes)
            cb.toggled.connect(self._on_received_lang_check_toggled)
            self.received_lang_checks[code] = cb
            grid.addWidget(cb, i // cols, i % cols)

        scroll.setWidget(inner)
        content.addWidget(scroll)

    def _selected_received_langs(self):
        # RECEIVED_LANG_ITEMS define a ordem = prioridade de tentativa
        return [code for code, cb in self.received_lang_checks.items() if cb.isChecked()]

    def _on_received_lang_check_toggled(self, _checked):
        self._persist_settings()

    def _build_labeled_slider(self, content, label_text, min_v, max_v, default_v, tooltip=None, value_fmt=None):
        value_fmt = value_fmt or (lambda v: str(v))
        row = QHBoxLayout()
        row.addWidget(self._row_label(label_text))
        row.addStretch(1)
        value_lbl = QLabel(value_fmt(default_v))
        value_lbl.setStyleSheet(f"color: {ACCENT}; font-weight: 700; background: transparent;")
        row.addWidget(value_lbl)
        content.addLayout(row)

        slider = QSlider(Qt.Horizontal)
        slider.setRange(min_v, max_v)
        slider.setValue(default_v)
        if tooltip:
            slider.setToolTip(tooltip)
        slider.valueChanged.connect(lambda v: value_lbl.setText(value_fmt(v)))
        content.addWidget(slider)
        return slider

    def _enumerate_audio_devices(self):
        """Popula self.inputs/self.outputs — chamado uma unica vez em
        __init__, ANTES de construir qualquer painel, pra estar disponivel
        tanto pro painel de configuracoes quanto pro painel esquerdo.

        No Windows, o PortAudio expõe cada dispositivo FISICO separadamente
        por API de audio (MME, DirectSound, WASAPI, WDM-KS) — o mesmo
        aparelho aparecia varias vezes na lista, com nomes truncados/
        diferentes conforme a API. A tentativa anterior de resolver isso
        filtrando SO WASAPI causou uma regressao seria: pelo menos um
        dispositivo real (Fifine K420) reporta um defaultSampleRate ERRADO
        na variante WASAPI (16000Hz) contra o correto na variante MME
        (44100Hz) — usar a variante WASAPI deixou o reconhecimento de fala
        muito pior (audio mal amostrado). Entao agora: mantemos MME/
        DirectSound/WASAPI (nessa ordem de preferencia — MME primeiro, que e
        historicamente o mais compativel) e so excluimos WDM-KS (a API de
        acesso EXCLUSIVO, que falha se outro programa ja estiver usando o
        dispositivo). A deduplicacao reconhece nomes truncados entre APIs
        (ex: "Realtek Digital Output (Realtek" e "Realtek Digital Output
        (Realtek(R) Audio)" sao o MESMO aparelho) via prefixo, mantendo
        sempre a PRIMEIRA variante encontrada (MME, comprovadamente
        funcional) em vez de arriscar outra API com comportamento diferente.
        """
        devices = sd.query_devices()
        hostapis = sd.query_hostapis()
        excluded_hostapis = [i for i, h in enumerate(hostapis) if "wdm-ks" in h["name"].lower()]

        def _collect(channel_key):
            result = []
            for i, d in enumerate(devices):
                if d["hostapi"] in excluded_hostapis or d[channel_key] <= 0:
                    continue
                name = d["name"]
                if any(_same_device_name(name, existing) for _, existing in result):
                    continue
                result.append((i, name))
            return result

        self.inputs = _collect("max_input_channels")
        self.outputs = _collect("max_output_channels")

    def _build_audio_card(self):
        card, content = make_card("Dispositivos de Áudio")
        settings = self._settings

        content.addWidget(self._row_label("Microfone (reconhece minha fala)"))
        self.mic = ModernCombo(self, values=[f"{i} - {n}" for i, n in self.inputs])
        content.addWidget(self.mic)
        default_mic_idx = 0
        if "mic" in settings:
            for idx, (_, name) in enumerate(self.inputs):
                if _same_device_name(name, settings["mic"]):
                    default_mic_idx = idx
                    break
        if self.inputs:
            self.mic.setCurrentIndex(default_mic_idx)

        content.addWidget(self._row_label("Saída do TTS (VB-Cable / Headset)"))
        self.output = ModernCombo(self, values=[f"{i} - {n}" for i, n in self.outputs])
        content.addWidget(self.output)
        default_out_idx = 0
        if "out" in settings:
            for idx, (_, name) in enumerate(self.outputs):
                if _same_device_name(name, settings["out"]):
                    default_out_idx = idx
                    break
        if self.outputs:
            self.output.setCurrentIndex(default_out_idx)

        card.setMinimumHeight(122)
        return card

    def _build_language_voice_card(self):
        card, content = make_card("Idiomas e voz")
        content.setSpacing(3)
        settings = self._settings

        from_list = list(LANGS.keys())
        to_list = [k for k in LANGS.keys() if k != "Auto Detect"]

        content.addWidget(self._row_label("Origem (meu idioma)"))
        self.from_lang = ModernCombo(self, values=from_list)
        default_from_idx = 1
        if settings.get("from_lang") in from_list:
            default_from_idx = from_list.index(settings["from_lang"])
        self.from_lang.setCurrentIndex(default_from_idx)
        content.addWidget(self.from_lang)

        content.addWidget(self._row_label("Destino (idioma de quem me ouve)"))
        self.to_lang = ModernCombo(self, values=to_list)
        default_to_idx = 0
        if settings.get("to_lang") in to_list:
            default_to_idx = to_list.index(settings["to_lang"])
        self.to_lang.setCurrentIndex(default_to_idx)
        content.addWidget(self.to_lang)

        content.addWidget(self._row_label("Voz da minha fala"))
        self.my_voice_combo = ModernCombo(self, values=["-"])
        self.my_voice_combo.setToolTip(
            "Voz usada quando a SUA fala traduzida é falada em voz alta pro app. "
            "Muda de opções conforme o idioma escolhido em 'Destino'."
        )
        content.addWidget(self.my_voice_combo)

        self.pitch_slider = self._build_labeled_slider(
            content, "Pitch (tom de voz)", -50, 50, 0,
            tooltip="Ajusta o tom da voz sintetizada (grave a agudo) — não afeta vozes Kokoro",
        )
        hint_row = QHBoxLayout()
        grave = QLabel("Grave")
        grave.setObjectName("RowHint")
        agudo = QLabel("Agudo")
        agudo.setObjectName("RowHint")
        hint_row.addWidget(grave)
        hint_row.addStretch(1)
        hint_row.addWidget(agudo)
        content.addLayout(hint_row)

        self._refresh_voice_combo("my", self.to_lang.currentText())
        self.to_lang.currentTextChanged.connect(lambda t: self._refresh_voice_combo("my", t))
        self.my_voice_combo.currentTextChanged.connect(lambda _t: self._on_voice_combo_changed("my"))

        card.setMinimumHeight(234)
        return card

    @staticmethod
    def _voice_display_name(voice_id: str, engine_name: str) -> str:
        if engine_name == "edge":
            name = voice_id.split("-")[-1]
            if name.endswith("Neural"):
                name = name[:-len("Neural")]
            if name.endswith("Multilingual"):
                return f"{name[:-len('Multilingual')]} (Multilíngue)"
            return name
        return voice_id.split("_", 1)[-1].capitalize()

    def _voice_option_label(self, opt) -> str:
        gender_icon = "♀" if opt.gender == "F" else "♂"
        name = self._voice_display_name(opt.id, opt.engine)
        return f"{gender_icon} {name} — {opt.style}"

    def _refresh_voice_combo(self, role: str, lang_display_name: str):
        combo = self.my_voice_combo if role == "my" else self.received_voice_combo
        lang_code = LANGS.get(lang_display_name, "en")

        if lang_code == "auto":
            combo.set_values(["Automático — segue o idioma detectado"])
            combo.set_enabled(False)
            self._voice_combo_maps[role] = {}
            return

        combo.set_enabled(True)
        mapping = {}
        labels = []
        for opt in voice_options_for(lang_code):
            label = self._voice_option_label(opt)
            labels.append(label)
            mapping[label] = opt.id
        self._voice_combo_maps[role] = mapping
        combo.set_values(labels)

        saved_id = self._voice_overrides.get(normalize_lang_code(lang_code))
        if saved_id:
            saved_label = next((lbl for lbl, vid in mapping.items() if vid == saved_id), None)
            if saved_label:
                combo.setCurrentText(saved_label)

    def _on_voice_combo_changed(self, role: str):
        combo = self.my_voice_combo if role == "my" else self.received_voice_combo
        voice_id = self._voice_combo_maps.get(role, {}).get(combo.currentText())
        if not voice_id:
            return
        lang_display_name = self.to_lang.currentText() if role == "my" else self.from_lang.currentText()
        lang_code = normalize_lang_code(LANGS.get(lang_display_name, "en"))
        self._voice_overrides[lang_code] = voice_id
        self._persist_settings()

    def _resolve_voice(self, lang_code):
        lang_code = normalize_lang_code(lang_code)
        voice_id = self._voice_overrides.get(lang_code)
        if voice_id and find_voice_option(lang_code, voice_id):
            return voice_id
        return None

    def _toggle_row(self, content, icon_text, label_text, checked, tooltip=None):
        row = QHBoxLayout()
        lbl = QLabel(f"{icon_text}  {label_text}")
        lbl.setObjectName("RowLabel")
        row.addWidget(lbl)
        row.addStretch(1)
        switch = ToggleSwitch(checked=checked)
        if tooltip:
            switch.setToolTip(tooltip)
            lbl.setToolTip(tooltip)
        row.addWidget(switch)
        content.addLayout(row)
        return switch

    def _build_features_card(self):
        card, content = make_card("Recursos")
        settings = self._settings

        self.beep_switch = self._toggle_row(
            content, "🔔", "Som ao reconhecer fala", settings.get("beep", True),
            "Toca um bipe no seu headset quando a fala é reconhecida",
        )
        self.tts_switch = self._toggle_row(
            content, "🔊", "Voz (TTS)", settings.get("tts_voice", True),
            "Fala a tradução em voz alta no dispositivo de saída selecionado",
        )

        content.addWidget(self._row_label("Envio ao Chatbox (minha fala)"))
        self.chatbox_mode_combo = ModernCombo(self, values=CHATBOX_MODES)
        default_mode = settings.get("chatbox_mode")
        if default_mode not in CHATBOX_MODES:
            # migracao de um settings.json antigo (chatbox bool + dual_lang bool)
            if not settings.get("chatbox", True):
                default_mode = CHATBOX_MODE_OFF
            elif settings.get("dual_lang", True):
                default_mode = CHATBOX_MODE_BOTH
            else:
                default_mode = CHATBOX_MODE_TRANSLATED
        self.chatbox_mode_combo.setCurrentText(default_mode)
        self.chatbox_mode_combo.setToolTip("O que enviar ao chatbox do VRChat quando EU falo")
        content.addWidget(self.chatbox_mode_combo)

        # So o essencial (toggle + status, numa unica linha) fica sempre
        # visivel aqui. Tudo o resto (dispositivo, idioma, teste, overlay,
        # mute sync) mora no PAINEL LATERAL (_build_settings_panel), que abre
        # pra esquerda como um painel proprio — NUNCA aumenta a altura da
        # janela, so a largura (mesmo mecanismo do painel de conversa).
        divider = QLabel("FALA RECEBIDA")
        divider.setObjectName("CardTitle")
        content.addWidget(divider)

        listen_row = QHBoxLayout()
        listen_lbl = QLabel("🗣️  Ouvir outras pessoas")
        listen_lbl.setObjectName("RowLabel")
        listen_row.addWidget(listen_lbl)
        listen_row.addStretch(1)
        self._received_status_label = QLabel("● Parado")
        self._received_status_label.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 8pt; font-weight: 600; background: transparent;"
        )
        listen_row.addWidget(self._received_status_label)
        self.listen_others_switch = ToggleSwitch(checked=settings.get("listen_others", False))
        self.listen_others_switch.setToolTip(
            "Escuta o áudio que o VRChat está reproduzindo, reconhece e traduz a fala de outras pessoas"
        )
        listen_row.addWidget(self.listen_others_switch)
        content.addLayout(listen_row)
        self.listen_others_switch.toggled.connect(self._on_listen_others_toggled)
        self._apply_listen_others(self.listen_others_switch.isChecked())

        card.setMinimumHeight(178)
        return card

    def _update_settings_button_text(self):
        self.received_advanced_btn.setText("⚙  OCULTAR CONFIGURAÇÕES" if self.settings_open else "⚙  MOSTRAR CONFIGURAÇÕES")

    def _build_settings_panel(self):
        """Painel lateral com tudo que e configurado uma vez e raramente
        mexido de novo (dispositivo/idioma recebido, teste, overlay, mute
        sync). Abre pra ESQUERDA (a janela ancora a borda direita e cresce),
        nunca mexendo na altura da janela — resolve o problema de a janela
        ficar mais alta que a tela."""
        panel = QWidget()
        panel.setFixedWidth(SETTINGS_PANEL_WIDTH)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        settings = self._settings

        card, content = make_card("Fala Recebida — Config.")
        # card ja tinha bastante conteudo e ganhou mais uma linha (voz da fala
        # recebida) — aperta margens/espacamento so DESTE card pra caber tudo
        content.setSpacing(2)
        card.layout().setContentsMargins(14, 4, 14, 4)
        card.layout().setSpacing(2)

        content.addWidget(self._row_label("Áudio recebido (o que o VRChat reproduz)"))
        self.loopback_devices = list_loopback_devices()
        loopback_labels = [d.name for d in self.loopback_devices] or ["Nenhum dispositivo encontrado"]
        self.received_device_combo = ModernCombo(self, values=loopback_labels)
        content.addWidget(self.received_device_combo)
        default_received = settings.get("received_device")
        if not default_received or default_received not in loopback_labels:
            default_dev = get_default_loopback_device()
            if default_dev and default_dev.name in loopback_labels:
                default_received = default_dev.name
        if default_received in loopback_labels:
            self.received_device_combo.setCurrentText(default_received)

        content.addWidget(self._row_label("Fonte do áudio"))
        self.received_source_mode_combo = ModernCombo(self, values=SOURCE_MODES)
        self.received_source_mode_combo.setToolTip(
            "'Todo o áudio do computador' é o modo de sempre. 'Aplicativo específico' "
            "escuta só o programa escolhido abaixo (ex: só o VRChat), ignorando os outros."
        )
        content.addWidget(self.received_source_mode_combo)
        saved_mode_key = settings.get("speaker_audio_source_mode", "full_device")
        self.received_source_mode_combo.setCurrentText(
            SOURCE_MODE_KEY_TO_DISPLAY.get(saved_mode_key, SOURCE_MODE_FULL_DEVICE)
        )

        app_row = QHBoxLayout()
        app_row.setSpacing(6)
        app_labels, self._app_picker_map = self._build_app_picker_labels(list_audio_session_apps())
        self.received_app_combo = ModernCombo(self, values=app_labels)
        self.received_app_combo.setToolTip(
            "Só usado no modo 'Aplicativo específico' — escolha o programa cujo áudio "
            "você quer escutar (ex: VRChat.exe). Clique em 🔄 pra atualizar a lista."
        )
        app_row.addWidget(self.received_app_combo, 1)
        self.refresh_apps_btn = QPushButton("🔄")
        self.refresh_apps_btn.setObjectName("Ghost")
        self.refresh_apps_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_apps_btn.setFixedSize(34, 27)
        self.refresh_apps_btn.setToolTip("Reconsulta os programas abertos com sessão de áudio agora")
        app_row.addWidget(self.refresh_apps_btn, 0)
        content.addLayout(app_row)
        saved_exe = settings.get("speaker_target_executable")
        if saved_exe:
            saved_label = next((lbl for lbl, exe in self._app_picker_map.items() if exe == saved_exe), None)
            if saved_label:
                self.received_app_combo.setCurrentText(saved_label)

        is_app_mode = self._current_source_mode_key() == "application"
        self.received_app_combo.set_enabled(is_app_mode)
        self.refresh_apps_btn.setEnabled(is_app_mode)

        self.received_source_mode_combo.currentTextChanged.connect(self._on_source_mode_changed)
        self.received_app_combo.currentTextChanged.connect(self._on_target_app_changed)
        self.refresh_apps_btn.clicked.connect(self._on_refresh_apps_clicked)

        content.addWidget(self._row_label("Idiomas candidatos (marque um ou mais)"))
        self._build_received_lang_checklist(content, self._initial_received_langs(settings))

        test_row = QHBoxLayout()
        self.test_received_btn = QPushButton("🎚 Testar áudio recebido")
        self.test_received_btn.setObjectName("Ghost")
        self.test_received_btn.setCursor(Qt.PointingHandCursor)
        self.test_received_btn.setFixedHeight(34)
        self.test_received_btn.setToolTip("Grava alguns segundos, mostra o nível de áudio e tenta reconhecer uma frase (sem salvar nada em disco)")
        self.test_received_btn.clicked.connect(self._on_test_received_clicked)
        test_row.addWidget(self.test_received_btn)
        content.addLayout(test_row)

        self.received_level_meter = LevelMeter()
        content.addWidget(self.received_level_meter)

        self.received_tts_switch = self._toggle_row(
            content, "🔊", "Também falar em voz alta (TTS)", settings.get("received_tts", False),
            "Por padrão a fala recebida NÃO é reproduzida por voz — ative se quiser ouvir também",
        )

        content.addWidget(self._row_label("Saída da fala recebida (seu fone/headset — NUNCA o cabo virtual)"))
        received_out_labels = [f"{i} - {n}" for i, n in self.outputs]
        self.received_tts_output_combo = ModernCombo(self, values=received_out_labels)
        self.received_tts_output_combo.setToolTip(
            "Onde a TRADUÇÃO DO QUE OS OUTROS FALAM é tocada em voz. Use seu fone/headset "
            "real (ou o áudio do VR) — se apontar pro mesmo cabo virtual da SUA fala, você "
            "nunca ouve e o VRChat manda essa fala de volta pros outros como se fosse sua."
        )
        content.addWidget(self.received_tts_output_combo)

        received_voice_row = QHBoxLayout()
        received_voice_row.setSpacing(6)
        received_voice_label = QLabel("Voz:")
        received_voice_label.setObjectName("RowHint")
        received_voice_row.addWidget(received_voice_label, 0)
        self.received_voice_combo = ModernCombo(self, values=["-"])
        self.received_voice_combo.setToolTip(
            "Voz usada quando a fala RECEBIDA (já traduzida pro seu idioma) é falada em "
            "voz alta aqui — a mesma fala que sai no dispositivo escolhido acima. Muda de "
            "opções conforme o idioma escolhido em 'Origem (meu idioma)'."
        )
        received_voice_row.addWidget(self.received_voice_combo, 1)
        content.addLayout(received_voice_row)
        # populado e conectado ao idioma "Origem" mais adiante em _build_ui(),
        # quando self.from_lang ja existe (esse painel e construido ANTES do
        # painel esquerdo, onde from_lang mora — ver _build_ui)

        saved_received_out = settings.get("received_tts_output")
        default_received_out = None
        if saved_received_out:
            saved_name = saved_received_out.split(" - ", 1)[1] if " - " in saved_received_out else saved_received_out
            default_received_out = next(
                (lbl for lbl in received_out_labels
                 if _same_device_name(lbl.split(" - ", 1)[1] if " - " in lbl else lbl, saved_name)),
                None,
            )
        if not default_received_out:
            # default sensato: primeiro dispositivo que NAO pareça ser um cabo virtual
            non_cable = next((lbl for lbl in received_out_labels if "cable" not in lbl.lower()), None)
            default_received_out = non_cable or (received_out_labels[0] if received_out_labels else None)
        if default_received_out in received_out_labels:
            self.received_tts_output_combo.setCurrentText(default_received_out)
        self._apply_received_tts_output()
        self.received_tts_output_combo.currentTextChanged.connect(self._on_received_tts_output_changed)

        card.setMinimumHeight(250)
        layout.addWidget(card)

        overlay_card, overlay_content = make_card("Overlay & VRChat")
        overlay_content.setSpacing(2)

        overlay_enabled = settings.get("overlay_enabled", False)
        self.overlay_switch = self._toggle_row(
            overlay_content, "🥽", "Ativar overlay da fala recebida", overlay_enabled,
            "Mostra a tradução da fala recebida numa janela flutuante ou dentro do headset",
        )
        self.overlay_switch.toggled.connect(self._on_overlay_toggled)

        # Os ajustes finos do overlay so fazem sentido com ele ligado — ficam
        # escondidos por padrao. Como este painel tem altura sobrando (o
        # painel esquerdo principal e mais alto), mostrar/esconder isso aqui
        # NUNCA precisa redimensionar a janela.
        self.overlay_settings_box = QWidget()
        overlay_settings_layout = QVBoxLayout(self.overlay_settings_box)
        overlay_settings_layout.setContentsMargins(0, 0, 0, 0)
        overlay_settings_layout.setSpacing(6)
        self.overlay_settings_box.setVisible(overlay_enabled)
        overlay_content.addWidget(self.overlay_settings_box)

        overlay_settings_layout.addWidget(self._row_label("Tipo de overlay"))
        self.overlay_backend_combo = ModernCombo(self, values=OVERLAY_BACKENDS)
        saved_backend = settings.get("overlay_backend", OVERLAY_BACKEND_DESKTOP)
        if saved_backend in OVERLAY_BACKENDS:
            self.overlay_backend_combo.setCurrentText(saved_backend)
        self.overlay_backend_combo.currentTextChanged.connect(lambda _t: self._apply_overlay_backend())
        overlay_settings_layout.addWidget(self.overlay_backend_combo)

        self.overlay_opacity_slider = self._build_labeled_slider(
            overlay_settings_layout, "Opacidade do overlay", 20, 100, int(settings.get("overlay_opacity", 90)),
            value_fmt=lambda v: f"{v}%",
        )
        self.overlay_opacity_slider.valueChanged.connect(lambda v: setattr(self.overlay_mgr, "opacity", v / 100.0))

        self.overlay_duration_slider = self._build_labeled_slider(
            overlay_settings_layout, "Tempo visível", 2, 30, int(settings.get("overlay_duration", 6)),
            value_fmt=lambda v: f"{v}s",
        )
        self.overlay_duration_slider.valueChanged.connect(lambda v: setattr(self.overlay_mgr, "duration_seconds", float(v)))
        self.overlay_duration_slider.setEnabled(not settings.get("overlay_always_visible", False))

        self.overlay_always_visible_switch = self._toggle_row(
            overlay_settings_layout, "♾️", "Sempre visível (não some sozinho)", settings.get("overlay_always_visible", False),
        )
        self.overlay_always_visible_switch.toggled.connect(self._on_overlay_always_visible_toggled)

        self.overlay_font_slider = self._build_labeled_slider(
            overlay_settings_layout, "Tamanho da fonte", 12, 36, int(settings.get("overlay_font_size", 20)),
            value_fmt=lambda v: f"{v}pt",
        )
        self.overlay_font_slider.valueChanged.connect(lambda v: setattr(self.overlay_mgr, "font_size", v))

        self.overlay_maxlines_slider = self._build_labeled_slider(
            overlay_settings_layout, "Máximo de linhas", 1, 8, int(settings.get("overlay_max_lines", 4)),
        )
        self.overlay_maxlines_slider.valueChanged.connect(lambda v: setattr(self.overlay_mgr, "max_lines", v))

        self.mute_sync_switch = self._toggle_row(
            overlay_content, "🔇", "Sincronizar mute do VRChat", settings.get("mute_sync", False),
            "Detecta quando meu microfone está mutado no VRChat (parâmetro OSC /avatar/parameters/MuteSelf)",
        )
        self.mute_sync_switch.toggled.connect(self._on_mute_sync_toggled)
        self._apply_mute_sync(self.mute_sync_switch.isChecked())

        self.mute_pause_mic_switch = self._toggle_row(
            overlay_content, "⏸", "Pausar meu microfone quando mutado", settings.get("mute_pause_mic", False),
            "Além de não enviar ao chatbox, para de escutar meu microfone enquanto eu estiver mutado (a fala recebida continua normalmente)",
        )

        # aplica valores iniciais no overlay_manager (os sliders acima so disparam
        # o valueChanged quando o VALOR muda, entao os defaults precisam ser
        # aplicados explicitamente aqui uma vez)
        self.overlay_mgr.opacity = self.overlay_opacity_slider.value() / 100.0
        self.overlay_mgr.duration_seconds = float(self.overlay_duration_slider.value())
        self.overlay_mgr.always_visible = self.overlay_always_visible_switch.isChecked()
        self.overlay_mgr.font_size = self.overlay_font_slider.value()
        self.overlay_mgr.max_lines = self.overlay_maxlines_slider.value()
        self.overlay_mgr.enabled = self.overlay_switch.isChecked()
        self._apply_overlay_backend()

        overlay_card.setMinimumHeight(250)
        layout.addWidget(overlay_card)
        layout.addStretch(1)

        return panel

    def _build_action_buttons(self):
        col = QVBoxLayout()
        col.setSpacing(7)

        self.start_btn = QPushButton("INICIAR TRADUÇÃO")
        self.start_btn.setCursor(Qt.PointingHandCursor)
        self.start_btn.setStyleSheet(PRIMARY_BTN_QSS)
        self.start_btn.setFixedHeight(44)
        self.start_btn.setToolTip("Iniciar ou parar a tradução (Ctrl+Espaço)")
        self.start_btn.clicked.connect(self.toggle_service)
        col.addWidget(self.start_btn)

        # Mesmo destaque estrutural do "Iniciar Tradução" (altura/largura/peso
        # de fonte), mas em cor propria (roxo, ja associado a "fala recebida"
        # em toda a UI) pra continuar lendo como acao secundaria, so que com
        # presenca visual forte — antes vivia pequeno dentro do card "Recursos".
        self.received_advanced_btn = QPushButton()
        self.received_advanced_btn.setObjectName("GhostAccent")
        self.received_advanced_btn.setCheckable(True)
        self.received_advanced_btn.setCursor(Qt.PointingHandCursor)
        self.received_advanced_btn.setFixedHeight(44)
        self.received_advanced_btn.setToolTip(
            "Abre as configurações da fala recebida: dispositivo/aplicativo de áudio, "
            "idiomas candidatos, teste de áudio, voz, overlay e sincronização de mute"
        )
        self.received_advanced_btn.setChecked(self.settings_open)
        self._update_settings_button_text()
        self.received_advanced_btn.toggled.connect(self._on_advanced_settings_toggled)
        col.addWidget(self.received_advanced_btn)

        # "Abrir conversa" tambem ganha destaque (cor de acento + icone) em vez
        # do cinza neutro do "Ghost" padrao — e a acao mais usada durante o uso
        # normal do app, nao devia competir visualmente com "Limpar Chatbox".
        self.open_panel_btn = QPushButton()
        self.open_panel_btn.setObjectName("GhostBlue")
        self.open_panel_btn.setCursor(Qt.PointingHandCursor)
        self.open_panel_btn.setFixedHeight(40)
        self.open_panel_btn.setToolTip("Abrir ou fechar o painel de conversa (Ctrl+L)")
        self.open_panel_btn.clicked.connect(self._toggle_conversation_panel)
        col.addWidget(self.open_panel_btn)
        self._update_panel_button_text()

        self.clear_btn = QPushButton("Limpar Chatbox do VRChat")
        self.clear_btn.setObjectName("Ghost")
        self.clear_btn.setCursor(Qt.PointingHandCursor)
        self.clear_btn.setFixedHeight(34)
        self.clear_btn.setToolTip("Envia uma mensagem vazia para limpar o chatbox atual do VRChat")
        self.clear_btn.clicked.connect(self.clear_chatbox)
        col.addWidget(self.clear_btn)

        return col

    def _update_panel_button_text(self):
        self.open_panel_btn.setText("💬 ◂  FECHAR CONVERSA" if self.panel_open else "💬 ▸  ABRIR CONVERSA")

    # ── janela compacta / expansivel ────────────────────────────────────────

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+L"), self, activated=self._toggle_conversation_panel)
        QShortcut(QKeySequence("Ctrl+K"), self, activated=self.history_panel.clear)
        QShortcut(QKeySequence("Ctrl+Space"), self, activated=self.toggle_service)
        QShortcut(QKeySequence(Qt.Key_Escape), self, activated=self._close_conversation_panel)

    def _current_target_width(self):
        """Soma a largura compacta com a largura extra de cada painel que
        estiver aberto no momento (configuracoes a esquerda, conversa a
        direita) — a altura nunca entra nessa conta, ela e fixa desde
        _finalize_initial_size()."""
        width = COMPACT_WIDTH
        if self.settings_open:
            width += SETTINGS_WIDTH_DELTA
        if self.panel_open:
            width += CONVERSATION_WIDTH_DELTA
        return width

    def _min_required_height(self):
        """Maior altura que a janela genuinamente precisa AGORA, dado o
        conteudo REAL e atual do left_container, do settings_panel e do
        history_panel. O conteudo do settings_panel e dinamico (ex.:
        overlay_settings_box liga/desliga independente do painel estar
        aberto ou fechado — ver _on_overlay_toggled), entao isso precisa
        ser reavaliado toda vez que um painel vai abrir, nao so uma vez
        no startup (ver _ensure_fixed_height)."""
        needed_left = self.left_container.sizeHint().height()
        needed_settings = self.settings_panel.layout().sizeHint().height()
        needed_history = self.history_panel.sizeHint().height()
        return max(needed_left, needed_settings, needed_history) + self._chrome_height

    def _ensure_fixed_height(self):
        """Chamado logo ANTES de cada animacao de abertura, antes de
        show_before()/setVisible(True) e antes de qualquer setGeometry. Se
        o conteudo real agora exigir mais altura do que self._fixed_height
        tem congelada, cresce self._fixed_height UMA VEZ aqui. Assim,
        quando o painel oculto vira visivel, o Qt nao encontra nada pra
        "corrigir" sozinho no meio da animacao — o pulo de altura e
        eliminado na raiz, em vez de tentarmos vencer uma corrida contra o
        auto-resize do layout do Qt depois do fato. So CRESCE, nunca
        encolhe (evita a janela diminuir sozinha e cortar conteudo que uma
        abertura anterior ja precisou)."""
        needed = self._min_required_height()
        if needed > self._fixed_height:
            self._fixed_height = needed

    def _finalize_initial_size(self):
        # 1) assenta a geometria compacta primeiro (paineis extras ainda ocultos) —
        #    a altura calculada aqui e DEFINITIVA e nunca mais muda em runtime.
        self.settings_panel.setVisible(False)
        self.history_panel.setVisible(False)
        self.adjustSize()
        height = self.height()

        # adjustSize() as vezes sub-estima por alguns pixels a altura que o
        # left_container (e, quando aberto, o painel de configuracoes)
        # realmente precisam (visto empiricamente com cards mais cheios) —
        # corrige aqui em vez de reajustar margens/espacamento de cada card
        # toda vez que um campo novo e adicionado no futuro. "chrome" e o
        # espaco que a janela gasta fora do left_container (cabecalho,
        # margens) — guardado pra _min_required_height() reusar sempre que
        # precisar reavaliar a altura (ver _ensure_fixed_height).
        self._chrome_height = height - self.left_container.height()
        height = max(height, self._min_required_height())

        self.setFixedSize(COMPACT_WIDTH, height)
        self._fixed_height = height
        self._current_width = COMPACT_WIDTH
        self._current_pos = self.pos()

        # 2) se o usuario tinha deixado algum painel aberto na ultima sessao,
        #    reaplica INSTANTANEAMENTE (sem animacao — so no primeiro show da
        #    janela), ancorando pela borda direita do estado compacto acima.
        if self.settings_open or self.panel_open:
            if self.settings_open:
                self.settings_panel.setVisible(True)
            if self.panel_open:
                self.history_panel.setVisible(True)
            target_width = self._current_target_width()
            right_edge = self._current_pos.x() + self._current_width
            new_x = right_edge - target_width
            self.setFixedSize(target_width, height)
            self.move(new_x, self._current_pos.y())
            self._current_width = target_width
            self._current_pos = QPoint(new_x, self._current_pos.y())

    def _restore_window_position(self):
        x = self._settings.get("window_x")
        y = self._settings.get("window_y")
        if x is not None and y is not None:
            point = QPoint(int(x), int(y))
            for screen in QGuiApplication.screens():
                if screen.availableGeometry().contains(point):
                    self.move(point)
                    return
        # sem posicao salva (ou posicao fora de qualquer monitor): abre centralizada
        self._center_on_screen()

    def _center_on_screen(self):
        screen = self.screen() or QGuiApplication.primaryScreen()
        if not screen:
            return
        geo = screen.availableGeometry()
        x = geo.x() + max((geo.width() - self.width()) // 2, 0)
        y = geo.y() + max((geo.height() - self.height()) // 2, 0)
        self.move(x, y)

    def _toggle_conversation_panel(self):
        if self._animating:
            return
        self._set_panel_open(not self.panel_open)

    def _close_conversation_panel(self):
        if self.panel_open and not self._animating:
            self._set_panel_open(False)

    def _set_panel_open(self, opening: bool):
        self.panel_open = opening
        self.header_status.setVisible(opening)
        self._update_panel_button_text()
        show_before = (lambda: self.history_panel.setVisible(True)) if opening else None
        on_finished = None if opening else self._hide_history_panel
        self._animate_to_width(self._current_target_width(), show_before=show_before, on_finished=on_finished)
        self._persist_settings()

    def _hide_history_panel(self):
        self.history_panel.setVisible(False)

    def _set_settings_open(self, opening: bool):
        self.settings_open = opening
        self._update_settings_button_text()
        show_before = (lambda: self.settings_panel.setVisible(True)) if opening else None
        on_finished = None if opening else self._hide_settings_panel
        self._animate_to_width(self._current_target_width(), show_before=show_before, on_finished=on_finished)
        self._persist_settings()

    def _hide_settings_panel(self):
        self.settings_panel.setVisible(False)

    def _animate_to_width(self, target_width, show_before=None, on_finished=None):
        """Anima a LARGURA da janela, ancorando a borda DIREITA (a janela
        cresce/encolhe sempre pra ESQUERDA — quem estiver mais a direita no
        layout, tipicamente a conversa, nunca se desloca; o painel de
        configuracoes, por vir primeiro no layout, "aparece" nesse espaco
        novo à esquerda sem deslocar o painel de controles principal).

        Usa self._current_width/_current_pos (rastreados por nos mesmos) em
        vez de ler self.geometry() diretamente: descobrimos que mostrar um
        filho recem-visivel (setVisible(True)) pode fazer o Qt forcar um
        reposicionamento/redimensionamento SINCRONO do layout quando o
        sizeHint do conteudo passa a exigir mais espaco que o maximumSize
        atual da janela — e isso corrompe silenciosamente a ancora se lermos
        self.geometry() depois disso. show_before() so roda DEPOIS de
        relaxarmos os limites de tamanho (setMinimumSize/setMaximumSize) pra
        cobrir o intervalo [inicio, alvo], e a geometria e reimposta
        explicitamente logo em seguida, entao qualquer ajuste automatico que
        o Qt tente fazer nesse meio-tempo e sobrescrito.
        """
        start_width = self._current_width
        if start_width == target_width:
            if show_before:
                show_before()
            if on_finished:
                on_finished()
            return

        # Le a posicao AO VIVO via self.geometry() — NAO via self.pos()/
        # self.x()/self.y() nem via self._current_pos. Descobrimos (nesta
        # mesma investigacao) que, neste ambiente Qt/Windows, self.pos()
        # fica preso no valor pedido pra self.move() de antes da janela ser
        # mostrada de verdade e NUNCA se atualiza sozinho, enquanto
        # self.geometry() reflete a posicao real da area util — as duas
        # podem divergir por dezenas de pixels (a altura da barra de
        # titulo) o tempo todo. setGeometry()/geometry() sao consistentes
        # entre si; setGeometry(x,y,...) seguido de geometry() devolve
        # exatamente (x,y,...). Usar self.pos() aqui alimentava
        # setGeometry() com uma posicao ja errada, e cada nova animacao
        # comecava a partir desse erro — exatamente o pulo relatado.
        geo = self.geometry()
        right_edge = geo.x() + start_width
        y = geo.y()

        # Revalida a altura ANTES de mostrar o painel oculto e ANTES de
        # qualquer chamada de geometria desta animacao (ver
        # _ensure_fixed_height) — sem isso, self._fixed_height podia estar
        # desatualizado (ex.: overlay ligado depois do startup) e o Qt
        # tentava "corrigir" sozinho no meio da animacao, causando o pulo
        # de altura reportado.
        self._ensure_fixed_height()
        height = self._fixed_height

        lo = min(start_width, target_width)
        hi = max(start_width, target_width)
        self.setMinimumSize(lo, height)
        self.setMaximumSize(hi, height)

        # Liga a rede de seguranca (ver moveEvent/resizeEvent/
        # _enforce_anim_geometry) ANTES de show_before(): fazer um painel
        # oculto ficar visivel pode, sozinho, disparar um reposicionamento/
        # redimensionamento do Qt/Windows que nem sequer passa pelas nossas
        # chamadas explicitas de setGeometry — na pratica isso se manifestava
        # como a janela "subir" alguns pixels durante a animacao e so voltar
        # ao lugar certo quando _finish() reimpunha a geometria no final.
        # Com a rede ativa desde ja, qualquer moveEvent/resizeEvent fora do
        # esperado e corrigido no mesmo ciclo, antes do usuario notar.
        self._animating = True
        self._anim_expected_geometry = (right_edge - start_width, y, start_width, height)

        if show_before:
            show_before()
        self.setGeometry(*self._anim_expected_geometry)

        self.open_panel_btn.setEnabled(False)
        self.received_advanced_btn.setEnabled(False)

        anim = QVariantAnimation(self)
        anim.setDuration(PANEL_ANIM_MS)
        anim.setEasingCurve(QEasingCurve.InOutCubic)
        anim.setStartValue(start_width)
        anim.setEndValue(target_width)

        def _apply(value):
            w = int(value)
            self._anim_expected_geometry = (right_edge - w, y, w, height)
            self.setGeometry(*self._anim_expected_geometry)

        anim.valueChanged.connect(_apply)

        def _finish():
            final_x = right_edge - target_width
            # se os dois paineis abertos ao mesmo tempo nao couberem mais na
            # tela crescendo so pra esquerda (janela ficaria parcialmente fora
            # da tela), abre mao da ancora exata e prende a borda esquerda no
            # limite visivel do monitor — melhor ancora imperfeita que janela
            # inacessivel atras da borda da tela.
            screen = self.screen() or QGuiApplication.primaryScreen()
            if screen:
                min_x = screen.availableGeometry().x()
                final_x = max(final_x, min_x)
            self._anim_expected_geometry = (final_x, y, target_width, height)
            self.setFixedSize(target_width, height)
            self.move(final_x, y)
            self._current_width = target_width
            self._current_pos = QPoint(final_x, y)
            self._animating = False
            self._anim_expected_geometry = None
            self.open_panel_btn.setEnabled(True)
            self.received_advanced_btn.setEnabled(True)
            if on_finished:
                on_finished()

        anim.finished.connect(_finish)
        self._active_anim = anim
        anim.start()

    def _enforce_anim_geometry(self):
        """Chamado de moveEvent/resizeEvent enquanto uma animacao de
        largura esta rolando: se o Qt/Windows moveu ou redimensionou a
        janela pra fora do que _animate_to_width pediu por ultimo, corrige
        de volta no mesmo ciclo — rede de seguranca contra o pulo de altura/
        posicao descrito em _animate_to_width."""
        if self._correcting_geometry or not self._animating or self._anim_expected_geometry is None:
            return
        # Compara via geometry() — self.x()/self.y() nao sao confiaveis
        # neste ambiente Qt/Windows (ver comentario no topo de
        # _animate_to_width); usa-los aqui faria esta funcao "corrigir"
        # a cada moveEvent/resizeEvent mesmo sem nada de errado.
        actual = self.geometry()
        expected = self._anim_expected_geometry
        if (actual.x(), actual.y(), actual.width(), actual.height()) != expected:
            self._correcting_geometry = True
            self.setGeometry(*expected)
            self._correcting_geometry = False

    def moveEvent(self, event):
        super().moveEvent(event)
        self._enforce_anim_geometry()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._enforce_anim_geometry()

    # ── persistencia ─────────────────────────────────────────────────────

    def _persist_settings(self):
        mic_text = self.mic.currentText()
        out_text = self.output.currentText()
        mic_name = mic_text.split(" - ", 1)[1] if " - " in mic_text else mic_text
        out_name = out_text.split(" - ", 1)[1] if " - " in out_text else out_text
        pos = self.pos()

        self._settings = {
            "mic": mic_name,
            "out": out_name,
            "from_lang": self.from_lang.currentText(),
            "to_lang": self.to_lang.currentText(),
            "beep": self.beep_switch.isChecked(),
            "tts_voice": self.tts_switch.isChecked(),
            "chatbox_mode": self.chatbox_mode_combo.currentText(),
            "panel_open": self.panel_open,
            "settings_open": self.settings_open,
            "window_x": pos.x(),
            "window_y": pos.y(),

            "listen_others": self.listen_others_switch.isChecked(),
            "received_device": self.received_device_combo.currentText(),
            "speaker_audio_source_mode": self._current_source_mode_key(),
            "speaker_target_executable": self._current_target_executable() or self._settings.get("speaker_target_executable"),
            "received_langs": self._selected_received_langs(),
            "received_tts": self.received_tts_switch.isChecked(),
            "received_tts_output": self.received_tts_output_combo.currentText(),

            "overlay_enabled": self.overlay_switch.isChecked(),
            "overlay_backend": self.overlay_backend_combo.currentText(),
            "overlay_opacity": self.overlay_opacity_slider.value(),
            "overlay_duration": self.overlay_duration_slider.value(),
            "overlay_always_visible": self.overlay_always_visible_switch.isChecked(),
            "overlay_font_size": self.overlay_font_slider.value(),
            "overlay_max_lines": self.overlay_maxlines_slider.value(),

            "mute_sync": self.mute_sync_switch.isChecked(),
            "mute_pause_mic": self.mute_pause_mic_switch.isChecked(),

            "voice_overrides": self._voice_overrides,
        }
        save_settings(self._settings)

    # ── logica de negocio — minha fala (fluxo 1, inalterado na essencia) ───

    def _set_status(self, text, color):
        self.header_status.set_status(text, color)
        self.history_panel.set_status(text, color)

    def toggle_service(self):
        if not self.running:
            try:
                mic_index = int(self.mic.currentText().split(" - ")[0])
                out_index = int(self.output.currentText().split(" - ")[0])
            except (IndexError, ValueError):
                self.status_signal.emit("Erro: selecione microfone e saída!", DANGER)
                return

            engine.set_output_index(out_index)
            self.mic_index = mic_index

            self.status_signal.emit(*STATUS_STATES[STATUS_LISTENING])
            self.start_btn.setText("PARAR TRADUÇÃO")
            self.start_btn.setStyleSheet(DANGER_BTN_QSS)
            self.mic.set_enabled(False)
            self.output.set_enabled(False)

            self.running = True
            self._persist_settings()
            threading.Thread(target=self.run_engine, daemon=True).start()
        else:
            self.running = False
            self.status_signal.emit("Parando serviço...", WARNING)
            self.start_btn.setEnabled(False)
            self.start_btn.setText("Aguarde...")
            QTimer.singleShot(1500, self._reenable)

    def _reenable(self):
        self.start_btn.setEnabled(True)
        self.start_btn.setText("INICIAR TRADUÇÃO")
        self.start_btn.setStyleSheet(PRIMARY_BTN_QSS)
        self.status_signal.emit(*STATUS_STATES[STATUS_STOPPED])
        self.mic.set_enabled(True)
        self.output.set_enabled(True)

    def clear_chatbox(self):
        try:
            from core.osc import send_chat
            send_chat("")
            self.status_signal.emit("Chatbox limpo!", ACCENT)
        except Exception as e:
            self.status_signal.emit(f"Erro ao limpar: {e}", DANGER)

    def _replay_entry(self, entry: HistoryEntry):
        text = entry.translated if (entry.category == CATEGORY_TRANSLATED and entry.translated) else entry.original
        lang_code = entry.target_lang_code or LANGS.get(self.to_lang.currentText(), "en")
        pitch = self.pitch_slider.value()
        # fala RECEBIDA toca no dispositivo de fala recebida (meu fone/headset);
        # minha propria fala toca no "Saída do TTS" de sempre (engine default)
        engine_instance = self.received_tts_engine if entry.category == CATEGORY_RECEIVED else None
        voice = self._resolve_voice(lang_code)
        threading.Thread(
            target=self._speak_async, args=(text, lang_code, pitch, engine_instance, voice), daemon=True,
        ).start()

    @staticmethod
    def _speak_async(text, lang_code, pitch, engine_instance=None, voice=None):
        from core.tts import speak
        speak(text, lang_code, pitch, engine_instance=engine_instance, voice=voice)

    def _is_chatbox_muted(self) -> bool:
        return self.mute_sync_switch.isChecked() and self._vrchat_muted

    def run_engine(self):
        from core.speech_to_text import listen, adjust_noise
        from core.translate import translate
        from core.tts import speak
        from core.osc import send_chat
        from core.beep import beep_start, beep_done

        adjust_noise(self.mic_index)

        while self.running:
            if (self.mute_sync_switch.isChecked() and self.mute_pause_mic_switch.isChecked()
                    and self._vrchat_muted):
                time.sleep(0.3)
                continue

            try:
                current_from = LANGS.get(self.from_lang.currentText(), "pt")
                text = listen(self.mic_index, current_from)

                if not self.running:
                    break
                if not text:
                    continue

                current_to_label = self.to_lang.currentText()
                current_to = LANGS.get(current_to_label, "en")
                current_pitch = self.pitch_slider.value()
                source_lang_label = self.from_lang.currentText()
                if source_lang_label == "Auto Detect":
                    source_lang_label = None

                if self.beep_switch.isChecked():
                    threading.Thread(target=beep_start, daemon=True).start()
                    threading.Thread(target=beep_done, daemon=True).start()

                lang_from_code = current_from if current_from != "auto" else None
                same_lang = (lang_from_code == current_to)
                ts = time.strftime("%H:%M:%S")
                muted = self._is_chatbox_muted()
                mode = self.chatbox_mode_combo.currentText()
                will_tts = self.tts_switch.isChecked()

                if same_lang:
                    sent = False
                    if not muted and mode != CHATBOX_MODE_OFF:
                        send_chat(text)
                        sent = True
                    self.history_panel.add_entry(HistoryEntry(
                        timestamp=ts, category=CATEGORY_SAME_LANG, speaker="Você", source=SOURCE_LOCAL,
                        original=text, source_language=source_lang_label,
                        sent_to_chatbox=sent, tts_played=will_tts,
                    ))
                    if will_tts:
                        speak(text, current_to, current_pitch, voice=self._resolve_voice(current_to))
                else:
                    # revertido pra "auto" por pedido do usuario: passar a lingua
                    # de origem explicita (lang_from_code) piorou a traducao da
                    # MINHA fala pros outros — provavelmente porque "Origem (meu
                    # idioma)" e uma escolha manual grosseira (nao verificada
                    # contra o texto reconhecido, ao contrario do matched_language
                    # da fala recebida, que passa por confirmacao via langdetect
                    # quando ha 2+ candidatas). O auto-detect do Google Translate
                    # direto no texto reconhecido deu resultado melhor aqui.
                    translated = translate(text, current_to)
                    sent = False
                    if not muted:
                        if mode == CHATBOX_MODE_ORIGINAL:
                            send_chat(text); sent = True
                        elif mode == CHATBOX_MODE_TRANSLATED:
                            send_chat(translated); sent = True
                        elif mode == CHATBOX_MODE_BOTH:
                            send_chat(f"({text}) → {translated}"); sent = True

                    self.history_panel.add_entry(HistoryEntry(
                        timestamp=ts, category=CATEGORY_TRANSLATED, speaker="Você", source=SOURCE_LOCAL,
                        original=text, translated=translated,
                        target_lang=current_to_label, target_lang_code=current_to,
                        source_language=source_lang_label,
                        sent_to_chatbox=sent, tts_played=will_tts,
                    ))
                    if will_tts:
                        speak(translated, current_to, current_pitch, voice=self._resolve_voice(current_to))
            except Exception as e:
                ts = time.strftime("%H:%M:%S")
                self.history_panel.add_entry(HistoryEntry(
                    timestamp=ts, category=CATEGORY_ERROR, speaker="Sistema", original=str(e),
                ))
                self.status_signal.emit(*STATUS_STATES[STATUS_ERROR])
                time.sleep(0.5)

    # ── logica de negocio — fala recebida (fluxo 2, independente) ──────────

    def _get_selected_loopback_device(self):
        label = self.received_device_combo.currentText()
        return find_loopback_device_by_name(label) if label else None

    def _on_advanced_settings_toggled(self, checked):
        if checked == self.settings_open:
            return
        self._set_settings_open(checked)

    def _set_received_langs_enabled(self, enabled: bool):
        for cb in self.received_lang_checks.values():
            cb.setEnabled(enabled)

    # ── fonte do audio (todo o computador vs. aplicativo especifico) ───────

    def _build_app_picker_labels(self, apps):
        """(labels, label->executavel). Se o app salvo em settings.json nao
        estiver na lista AO VIVO, adiciona uma entrada sintetica pra nao
        perder a selecao — o app so ainda nao esta aberto, e isso NAO deve
        reverter silenciosamente pro modo 'todo o computador'."""
        labels = []
        mapping = {}
        for app in apps:
            label = f"{app.display_name} — {app.executable}"
            labels.append(label)
            mapping[label] = app.executable
        saved_exe = self._settings.get("speaker_target_executable")
        if saved_exe and saved_exe not in mapping.values():
            label = f"{saved_exe}{WAITING_APP_SUFFIX}"
            labels.insert(0, label)
            mapping[label] = saved_exe
        if not labels:
            labels = ["Nenhum aplicativo encontrado"]
        return labels, mapping

    def _current_source_mode_key(self) -> str:
        return SOURCE_MODE_DISPLAY_TO_KEY.get(self.received_source_mode_combo.currentText(), "full_device")

    def _current_target_executable(self):
        return self._app_picker_map.get(self.received_app_combo.currentText())

    def _set_app_picker_enabled(self, is_app_mode: bool):
        self.received_app_combo.set_enabled(is_app_mode)
        self.refresh_apps_btn.setEnabled(is_app_mode)
        self._refresh_test_button_enabled()

    def _refresh_test_button_enabled(self):
        is_app_mode = self._current_source_mode_key() == "application"
        self.test_received_btn.setEnabled(not is_app_mode and not self.listen_others_switch.isChecked())

    def _on_refresh_apps_clicked(self):
        apps = list_audio_session_apps()
        labels, mapping = self._build_app_picker_labels(apps)
        self._app_picker_map = mapping
        current = self.received_app_combo.currentText()
        self.received_app_combo.set_values(labels, keep_selection=True)
        if current not in labels and labels:
            self.received_app_combo.setCurrentIndex(0)
        if not apps:
            self.received_status_signal.emit("Nenhum aplicativo com sessão de áudio encontrado", WARNING)

    def _on_source_mode_changed(self, _text):
        self._set_app_picker_enabled(self._current_source_mode_key() == "application")
        self._persist_settings()
        self._restart_listening_if_active()

    def _on_target_app_changed(self, _text):
        self._persist_settings()
        self._restart_listening_if_active()

    def _restart_listening_if_active(self):
        if not self.listen_others_switch.isChecked():
            return
        self._apply_listen_others(False)
        self._apply_listen_others(True)

    def _build_audio_source(self):
        """Monta a fonte certa pro modo/selecao atual. Retorna (source, erro) —
        so um dos dois e nao-None."""
        if self._current_source_mode_key() == "application":
            exe = self._current_target_executable() or self._settings.get("speaker_target_executable")
            if not exe:
                return None, "Selecione um aplicativo específico"
            return ApplicationAudioSource(exe), None
        device = self._get_selected_loopback_device()
        if device is None:
            return None, "Selecione um dispositivo válido"
        return FullDeviceLoopbackSource(device), None

    def _apply_listen_others(self, checked):
        if checked:
            source, err = self._build_audio_source()
            if source is None:
                self.received_status_signal.emit(err, DANGER)
                self.listen_others_switch.setChecked(False)
                return
            candidates = self._selected_received_langs()
            if not candidates:
                self.received_status_signal.emit("Marque ao menos um idioma candidato", DANGER)
                self.listen_others_switch.setChecked(False)
                return
            self.speaker_service.candidate_languages = candidates
            self.speaker_service.target_language = LANGS.get(self.from_lang.currentText(), "pt")
            ok = self.speaker_service.start(source)
            if not ok:
                return  # on_error(fatal=True) ja avisou e desligou o switch
            if isinstance(source, FullDeviceLoopbackSource):
                self.received_status_signal.emit(*RECEIVED_STATUS_LISTENING)
            # ApplicationAudioSource ja emite o status certo sozinha (via on_source_status)
            # A combo de fonte/aplicativo fica LIGADA de proposito mesmo escutando —
            # trocar a fonte (ou o app) com "Ouvir Pessoas" ligado precisa funcionar
            # sem desligar antes (ver _restart_listening_if_active).
            self.received_device_combo.set_enabled(False)
            self._set_received_langs_enabled(False)
            self._refresh_test_button_enabled()
        else:
            self.speaker_service.stop()
            self.received_status_signal.emit(*RECEIVED_STATUS_STOPPED)
            self.received_device_combo.set_enabled(True)
            self.received_source_mode_combo.set_enabled(True)
            self._set_app_picker_enabled(self._current_source_mode_key() == "application")
            self._set_received_langs_enabled(True)
            self.received_level_meter.set_level(0.0)

    def _on_listen_others_toggled(self, checked):
        self._apply_listen_others(checked)
        self._persist_settings()

    def _on_source_status(self, msg: str):
        # "Aguardando X.exe..." e um estado de espera (cor de aviso); qualquer
        # outra mensagem da fonte (ex: "Ouvindo somente X.exe") e um estado
        # normal de funcionamento, mesma cor do "Ouvindo..." padrao.
        color = WARNING if msg.startswith("Aguardando") else RECEIVED_ACCENT
        self.received_status_signal.emit(msg, color)

    def _set_received_status(self, text, color):
        self._received_status_label.setText(f"● {text}")
        self._received_status_label.setStyleSheet(
            f"color: {color}; font-size: 8pt; font-weight: 600; background: transparent;"
        )

    def _on_speaker_error(self, message, fatal):
        self.received_status_signal.emit(*RECEIVED_STATUS_ERROR)
        ts = time.strftime("%H:%M:%S")
        self.history_panel.add_entry(HistoryEntry(
            timestamp=ts, category=CATEGORY_ERROR, speaker="Sistema (áudio recebido)", original=message,
        ))
        if fatal:
            self.listen_others_switch.setChecked(False)

    def _handle_received_translation(self, result):
        ts = result.timestamp
        entry = HistoryEntry(
            timestamp=ts, category=CATEGORY_RECEIVED, speaker="Recebido", source=SOURCE_RECEIVED,
            original=result.original_text, translated=result.translated_text,
            source_language=CODE_TO_LANG_NAME.get(result.source_language, result.source_language),
            target_lang=self.from_lang.currentText(), target_lang_code=result.target_language,
        )
        self.history_panel.add_entry(entry)
        self.received_status_signal.emit(*RECEIVED_STATUS_LISTENING)

        if self.overlay_switch.isChecked():
            self.overlay_mgr.show_text(result.translated_text)

        if self.received_tts_switch.isChecked():
            pitch = self.pitch_slider.value()
            voice = self._resolve_voice(result.target_language)
            threading.Thread(
                target=self._speak_async,
                args=(result.translated_text, result.target_language, pitch, self.received_tts_engine, voice),
                daemon=True,
            ).start()

    def _on_level_changed(self, level):
        self.received_level_meter.set_level(level)

    # ── teste de audio recebido ──────────────────────────────────────────

    def _on_test_received_clicked(self):
        if self.speaker_service.is_running():
            self.status_signal.emit("Pare a escuta contínua antes de testar (evita 2 capturas ao mesmo tempo).", WARNING)
            return
        device = self._get_selected_loopback_device()
        if device is None:
            self.status_signal.emit("Selecione um dispositivo de áudio recebido válido.", DANGER)
            return
        candidates = self._selected_received_langs()
        if not candidates:
            self.status_signal.emit("Marque ao menos um idioma candidato.", DANGER)
            return
        self.speaker_service.candidate_languages = candidates
        self.test_received_btn.setEnabled(False)
        self.test_received_btn.setText("Testando (4s)...")
        self.received_level_meter.set_level(0.0)
        self.speaker_service.run_test(device, duration=4.0)

    def _on_test_result(self, text, error):
        self.test_received_btn.setEnabled(True)
        self.test_received_btn.setText("🎚 Testar áudio recebido")
        if error:
            self.status_signal.emit(f"Teste falhou: {error}", DANGER)
        elif text:
            preview = text if len(text) <= 60 else text[:57] + "..."
            matched = self.speaker_service.last_test_matched_language
            lang_name = CODE_TO_LANG_NAME.get(matched, "")
            prefix = f"[{lang_name}] " if lang_name and len(self._selected_received_langs()) > 1 else ""
            self.status_signal.emit(f'Teste OK: {prefix}"{preview}"', ACCENT)
        else:
            self.status_signal.emit("Teste: nenhuma fala reconhecida (silêncio ou ruído baixo, ou nenhuma candidata bateu).", WARNING)

    def _on_loopback_devices_changed(self):
        self.loopback_devices = list_loopback_devices()
        labels = [d.name for d in self.loopback_devices] or ["Nenhum dispositivo encontrado"]
        self.received_device_combo.set_values(labels, keep_selection=True)

    # ── overlay ──────────────────────────────────────────────────────────

    def _apply_received_tts_output(self, _text=None):
        label = self.received_tts_output_combo.currentText()
        if not label:
            return
        try:
            index = int(label.split(" - ", 1)[0])
        except ValueError:
            return
        self.received_tts_engine.set_output_index(index)

    def _on_received_tts_output_changed(self, _text):
        self._apply_received_tts_output()
        self._persist_settings()

    def _apply_overlay_backend(self):
        wants_openvr = self.overlay_backend_combo.currentText() == OVERLAY_BACKEND_OPENVR
        name = "openvr" if wants_openvr else "desktop"
        ok = self.overlay_mgr.select_backend(name)
        if not ok and wants_openvr:
            self.status_signal.emit("SteamVR não detectado — usando overlay de desktop.", WARNING)
            self.overlay_mgr.select_backend("desktop")

    def _on_overlay_toggled(self, checked):
        self.overlay_mgr.enabled = checked
        if not checked:
            self.overlay_mgr.hide()
        self.overlay_settings_box.setVisible(checked)
        # Este switch mora DENTRO do settings_panel — dá pra ligar/desligar
        # com o painel ja aberto (janela em repouso, fora de qualquer
        # animacao). Isso muda a altura real que o settings_panel precisa
        # (overlay_settings_box soma ~6 linhas), entao revalida aqui tambem
        # — nao so em _animate_to_width — senao a proxima abertura carrega
        # uma self._fixed_height desatualizada e o pulo de altura volta.
        if self.settings_open and not self._animating:
            self._ensure_fixed_height()
            if self.height() != self._fixed_height:
                self.setFixedSize(self._current_width, self._fixed_height)
        self._persist_settings()

    def _on_overlay_always_visible_toggled(self, checked):
        self.overlay_mgr.set_always_visible(checked)
        self.overlay_duration_slider.setEnabled(not checked)

    # ── mute sync ────────────────────────────────────────────────────────

    def _apply_mute_sync(self, checked):
        if checked:
            self.osc_receiver.start()
        else:
            self.osc_receiver.stop()
            self._vrchat_muted = False

    def _on_mute_sync_toggled(self, checked):
        self._apply_mute_sync(checked)
        self._persist_settings()

    def _on_mute_changed(self, muted):
        self._vrchat_muted = muted
        if muted:
            self.status_signal.emit("Microfone mutado no VRChat", WARNING)

    def closeEvent(self, event):
        self.running = False
        self.speaker_service.stop()
        self.osc_receiver.stop()
        self.device_monitor.stop()
        self.overlay_mgr.shutdown()
        self._persist_settings()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
