import tkinter as tk
import threading
import sounddevice as sd
import sys, os
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.singleton import engine
from core.languages import LANGS
from core.voices import VOICES

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "settings.json")


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


# ─────────────────────────────────────────────────────────────────────────────
#  VRCombobox — dropdown personalizado compatível com overlays de VR
#  Usa Toplevel always-on-top em vez do popup nativo do Windows,
#  que não é renderizado corretamente por SteamVR/Quest Link/Vive.
# ─────────────────────────────────────────────────────────────────────────────
class VRCombobox(tk.Frame):
    def __init__(self, parent, values=None, width=45, **kwargs):
        super().__init__(parent, bg="#252525",
                         highlightbackground="#383838",
                         highlightthickness=1, **kwargs)
        self._values = list(values or [])
        self._current_idx = 0
        self._popup = None
        self._state = "normal"
        self._var = tk.StringVar()

        # Botão principal (texto selecionado)
        self._btn = tk.Button(
            self, textvariable=self._var,
            bg="#252525", fg="#FFFFFF",
            font=("Segoe UI", 9),
            activebackground="#333333", activeforeground="#FFFFFF",
            bd=0, relief="flat", anchor="w", cursor="hand2",
            command=self._toggle_popup
        )
        self._btn.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=2)

        # Botão seta
        self._arrow = tk.Button(
            self, text="▾", width=2,
            bg="#252525", fg="#666666",
            font=("Segoe UI", 10),
            activebackground="#333333",
            bd=0, relief="flat", cursor="hand2",
            command=self._toggle_popup
        )
        self._arrow.pack(side="right", padx=(0, 4), pady=2)

        if self._values:
            self._var.set(self._values[0])

    # ── Popup ────────────────────────────────────────────────────────────────

    def _toggle_popup(self):
        if self._state == "disabled":
            return
        if self._popup and self._popup.winfo_exists():
            self._close_popup()
            return
        self._show_popup()

    def _show_popup(self):
        # Posiciona o popup logo abaixo do widget
        self.update_idletasks()
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height()
        w = self.winfo_width()
        row_h = 24
        max_rows = min(10, len(self._values))
        h = max_rows * row_h + 4

        self._popup = tk.Toplevel()
        self._popup.wm_overrideredirect(True)   # sem barra de título
        self._popup.attributes("-topmost", True)  # SEMPRE sobre tudo (VR overlay)
        self._popup.geometry(f"{w}x{h}+{x}+{y}")
        self._popup.configure(bg="#1E1E1E",
                              highlightbackground="#4C8BF5",
                              highlightthickness=1)

        sb = tk.Scrollbar(self._popup, orient="vertical",
                          bg="#333333", troughcolor="#1E1E1E", width=10,
                          relief="flat")
        self._lb = tk.Listbox(
            self._popup,
            bg="#1E1E1E", fg="#FFFFFF",
            selectbackground="#4C8BF5", selectforeground="#FFFFFF",
            font=("Segoe UI", 9),
            bd=0, highlightthickness=0,
            activestyle="none",
            yscrollcommand=sb.set
        )
        sb.config(command=self._lb.yview)
        sb.pack(side="right", fill="y")
        self._lb.pack(side="left", fill="both", expand=True)

        for v in self._values:
            self._lb.insert("end", " " + v)

        if 0 <= self._current_idx < len(self._values):
            self._lb.selection_set(self._current_idx)
            self._lb.see(self._current_idx)

        self._lb.bind("<ButtonRelease-1>", self._on_select)
        self._lb.bind("<Return>", self._on_select)
        self._lb.bind("<Escape>", lambda e: self._close_popup())

        # Fecha ao perder foco
        self._popup.bind("<FocusOut>", self._on_focus_out)
        self._popup.focus_force()
        self._lb.focus_set()

    def _on_focus_out(self, event):
        # Pequeno delay para não fechar antes de processar o clique
        self._popup.after(100, self._close_popup)

    def _on_select(self, event=None):
        sel = self._lb.curselection()
        if sel:
            self._current_idx = sel[0]
            self._var.set(self._values[self._current_idx])
        self._close_popup()

    def _close_popup(self):
        try:
            if self._popup and self._popup.winfo_exists():
                self._popup.destroy()
        except Exception:
            pass
        self._popup = None

    # ── API compatível com ttk.Combobox ──────────────────────────────────────

    def get(self):
        return self._var.get()

    def current(self, idx=None):
        if idx is None:
            return self._current_idx
        self._current_idx = max(0, min(idx, len(self._values) - 1))
        if self._values:
            self._var.set(self._values[self._current_idx])

    def __setitem__(self, key, value):
        if key == "values":
            self._values = list(value)
            if self._values:
                self._var.set(self._values[self._current_idx]
                              if self._current_idx < len(self._values)
                              else self._values[0])
        else:
            super().__setitem__(key, value)

    def __getitem__(self, key):
        if key == "values":
            return self._values
        return super().__getitem__(key)

    def config(self, **kwargs):
        state = kwargs.pop("state", None)
        if state == "disabled":
            self._state = "disabled"
            self._btn.config(state="disabled", fg="#444444", cursor="")
            self._arrow.config(state="disabled", fg="#444444", cursor="")
        elif state == "normal":
            self._state = "normal"
            self._btn.config(state="normal", fg="#FFFFFF", cursor="hand2")
            self._arrow.config(state="normal", fg="#666666", cursor="hand2")
        if kwargs:
            super().config(**kwargs)


# ─────────────────────────────────────────────────────────────────────────────
#  App principal
# ─────────────────────────────────────────────────────────────────────────────
class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Translator By: LeNinjaMK")
        self.root.geometry("420x800")
        self.root.resizable(False, False)
        self.root.configure(bg="#181818")

        self.running = False

        devices = sd.query_devices()
        settings = load_settings()

        lbl_opts = {"bg": "#181818", "fg": "#CCCCCC", "font": ("Segoe UI", 9, "bold")}

        # ── Título ───────────────────────────────────────────────────────────
        title_frame = tk.Frame(root, bg="#181818")
        title_frame.pack(pady=(20, 5))
        tk.Label(title_frame, text="VRChat Speech",
                 font=("Segoe UI", 22, "bold"), bg="#181818", fg="#FFFFFF").pack()
        tk.Label(title_frame, text="By: LeNinjaMK",
                 font=("Segoe UI", 10, "bold"), bg="#181818", fg="#4C8BF5").pack()

        tk.Label(root, text="Fale claramente e evite fontes de ruído de fundo.",
                 font=("Segoe UI", 9, "italic"), bg="#181818", fg="#888888").pack(pady=(0, 15))

        # ── Microfone (INPUT) ─────────────────────────────────────────────────
        tk.Label(root, text="Dispositivo de entrada (Microfone):", **lbl_opts).pack(anchor="w", padx=30, pady=(5, 2))
        _seen_in = set()
        self.inputs = []
        for i, d in enumerate(devices):
            if d["max_input_channels"] > 0 and d["name"] not in _seen_in:
                _seen_in.add(d["name"])
                self.inputs.append((i, d["name"]))

        self.mic = VRCombobox(root, width=45)
        self.mic["values"] = [f"{i} - {n}" for i, n in self.inputs]
        default_mic_idx = 0
        if "mic" in settings:
            for idx, (_, name) in enumerate(self.inputs):
                if name == settings["mic"]:
                    default_mic_idx = idx
                    break
        if self.inputs:
            self.mic.current(default_mic_idx)
        self.mic.pack(padx=30, fill="x", ipady=3)

        # ── Idioma de origem ─────────────────────────────────────────────────
        tk.Label(root, text="Idioma de origem:", **lbl_opts).pack(anchor="w", padx=30, pady=(12, 2))
        from_langs_list = list(LANGS.keys())
        self.from_lang = VRCombobox(root, width=45, values=from_langs_list)
        default_from_idx = 1
        if "from_lang" in settings and settings["from_lang"] in from_langs_list:
            default_from_idx = from_langs_list.index(settings["from_lang"])
        self.from_lang.current(default_from_idx)
        self.from_lang.pack(padx=30, fill="x", ipady=3)

        # ── Idioma de destino ────────────────────────────────────────────────
        tk.Label(root, text="Idioma de destino:", **lbl_opts).pack(anchor="w", padx=30, pady=(12, 2))
        to_langs_list = [k for k in LANGS.keys() if k != "Auto Detect"]
        self.to_lang = VRCombobox(root, width=45, values=to_langs_list)
        default_to_idx = 0
        if "to_lang" in settings and settings["to_lang"] in to_langs_list:
            default_to_idx = to_langs_list.index(settings["to_lang"])
        self.to_lang.current(default_to_idx)
        self.to_lang.pack(padx=30, fill="x", ipady=3)

        # ── Voice Pitch ──────────────────────────────────────────────────────
        tk.Label(root, text="Voice Pitch (Tom de Voz):", **lbl_opts).pack(anchor="w", padx=30, pady=(15, 2))
        slider_frame = tk.Frame(root, bg="#181818")
        slider_frame.pack(fill="x", padx=30)
        tk.Label(slider_frame, text="Grave", bg="#181818", fg="#777777",
                 font=("Segoe UI", 8, "bold")).pack(side="left")
        self.pitch_scale = tk.Scale(slider_frame, from_=-50, to=50, orient=tk.HORIZONTAL,
                                    bg="#181818", fg="#FFFFFF", highlightthickness=0,
                                    troughcolor="#252525", activebackground="#4C8BF5",
                                    showvalue=True, bd=0)
        self.pitch_scale.set(0)
        self.pitch_scale.pack(side="left", fill="x", expand=True, padx=8)
        tk.Label(slider_frame, text="Agudo", bg="#181818", fg="#777777",
                 font=("Segoe UI", 8, "bold")).pack(side="right")

        # ── Saída de áudio (OUTPUT) ──────────────────────────────────────────
        tk.Label(root, text="Dispositivo de saída (VB-Cable / Headset):", **lbl_opts).pack(anchor="w", padx=30, pady=(12, 2))
        _seen_out = set()
        self.outputs = []
        for i, d in enumerate(devices):
            if d["max_output_channels"] > 0 and d["name"] not in _seen_out:
                _seen_out.add(d["name"])
                self.outputs.append((i, d["name"]))

        self.out = VRCombobox(root, width=45)
        self.out["values"] = [f"{i} - {n}" for i, n in self.outputs]
        default_out_idx = 0
        if "out" in settings:
            for idx, (_, name) in enumerate(self.outputs):
                if name == settings["out"]:
                    default_out_idx = idx
                    break
        if self.outputs:
            self.out.current(default_out_idx)
        self.out.pack(padx=30, fill="x", ipady=3)

        # Espaçador
        tk.Frame(root, height=10, bg="#181818").pack()

        # ── Botão START ──────────────────────────────────────────────────────
        self.btn_start = tk.Button(root, text="START LISTENING",
                                   command=self.toggle_service,
                                   bg="#252525", fg="#FFFFFF",
                                   font=("Segoe UI", 11, "bold"),
                                   activebackground="#333333", activeforeground="#FFFFFF",
                                   bd=0, relief="flat", height=2, cursor="hand2")
        self.btn_start.pack(padx=30, fill="x", pady=(15, 8))

        # ── Botão Clear Chatbox ──────────────────────────────────────────────
        self.btn_clear = tk.Button(root, text="Clear Chatbox text",
                                   command=self.clear_chatbox,
                                   bg="#1F1F1F", fg="#888888", font=("Segoe UI", 9),
                                   activebackground="#252525", activeforeground="#CCCCCC",
                                   bd=0, relief="flat", height=1, cursor="hand2")
        self.btn_clear.pack(padx=30, fill="x", pady=(0, 6))

        # ── Checkbox Beep ────────────────────────────────────────────────────
        self.beep_var = tk.BooleanVar(value=settings.get("beep", True))
        beep_frame = tk.Frame(root, bg="#181818")
        beep_frame.pack(padx=30, fill="x", pady=(0, 6))
        tk.Checkbutton(
            beep_frame, text="✔ Som de aviso ao reconhecer fala",
            variable=self.beep_var,
            bg="#181818", fg="#888888",
            activebackground="#181818", activeforeground="#CCCCCC",
            selectcolor="#252525",
            font=("Segoe UI", 9), anchor="w", cursor="hand2"
        ).pack(side="left")

        # ── Toggle Buttons: TTS / Chatbox / Dual Language ────────────────────
        tk.Label(root, text="Ativar / Desativar recursos:",
                 bg="#181818", fg="#555555",
                 font=("Segoe UI", 8)).pack(anchor="w", padx=30, pady=(4, 2))

        toggles_frame = tk.Frame(root, bg="#181818")
        toggles_frame.pack(padx=30, fill="x", pady=(0, 8))

        self.tts_var       = tk.BooleanVar(value=settings.get("tts_voice", True))
        self.chatbox_var   = tk.BooleanVar(value=settings.get("chatbox",   True))
        self.dual_lang_var = tk.BooleanVar(value=settings.get("dual_lang", True))

        _A_BG, _A_FG = "#12334D", "#4C8BF5"
        _I_BG, _I_FG = "#1E1E1E", "#444444"

        def _make_toggle(parent, text, var):
            btn = tk.Button(
                parent, text=text,
                bg=_A_BG if var.get() else _I_BG,
                fg=_A_FG if var.get() else _I_FG,
                font=("Segoe UI", 8, "bold"),
                activebackground="#252525", activeforeground="#CCCCCC",
                bd=0, relief="flat", cursor="hand2", pady=6
            )
            def _toggle(b=btn, v=var):
                v.set(not v.get())
                b.config(bg=_A_BG if v.get() else _I_BG,
                         fg=_A_FG if v.get() else _I_FG)
            btn.config(command=_toggle)
            return btn

        self.btn_tts_toggle = _make_toggle(toggles_frame, "🔊 TTS Voice", self.tts_var)
        self.btn_tts_toggle.pack(side="left", expand=True, fill="x", padx=(0, 2))

        self.btn_chatbox_toggle = _make_toggle(toggles_frame, "💬 Chatbox", self.chatbox_var)
        self.btn_chatbox_toggle.pack(side="left", expand=True, fill="x", padx=2)

        self.btn_dual_toggle = _make_toggle(toggles_frame, "🌐 Dual Lang", self.dual_lang_var)
        self.btn_dual_toggle.pack(side="left", expand=True, fill="x", padx=(2, 0))

        # ── Status ───────────────────────────────────────────────────────────
        self.status = tk.Label(root, text="Parado",
                               font=("Segoe UI", 9), bg="#181818", fg="#666666")
        self.status.pack(pady=8)

    # ─────────────────────────────────────────────────────────────────────────

    def toggle_service(self):
        if not self.running:
            try:
                mic_index = int(self.mic.get().split(" - ")[0])
                out_index = int(self.out.get().split(" - ")[0])
            except (IndexError, ValueError, AttributeError):
                self.status.config(text="Erro: Selecione microfone e saída!", fg="#FF3333")
                return

            engine.set_output_index(out_index)
            self.mic_index = mic_index

            try:
                mic_name = self.mic.get().split(" - ", 1)[1]
            except IndexError:
                mic_name = self.mic.get()
            try:
                out_name = self.out.get().split(" - ", 1)[1]
            except IndexError:
                out_name = self.out.get()

            save_settings({
                "mic":       mic_name,
                "out":       out_name,
                "from_lang": self.from_lang.get(),
                "to_lang":   self.to_lang.get(),
                "beep":      self.beep_var.get(),
                "tts_voice": self.tts_var.get(),
                "chatbox":   self.chatbox_var.get(),
                "dual_lang": self.dual_lang_var.get()
            })

            self.status.config(text="Escutando...", fg="#4C8BF5")
            self.btn_start.config(text="STOP LISTENING", bg="#A31D1D")
            self.mic.config(state="disabled")
            self.out.config(state="disabled")

            self.running = True
            threading.Thread(target=self.run_engine, daemon=True).start()
        else:
            self.running = False
            self.status.config(text="Parando serviço...", fg="#FFA500")
            self.btn_start.config(state="disabled", text="Aguarde...", bg="#333333")

            def reenable():
                self.btn_start.config(state="normal", text="START LISTENING", bg="#252525")
                self.status.config(text="Parado", fg="#666666")
                self.mic.config(state="normal")
                self.out.config(state="normal")

            self.root.after(1500, reenable)

    def clear_chatbox(self):
        try:
            from core.osc import send_chat
            send_chat("")
            self.status.config(text="Chatbox limpo!", fg="#4C8BF5")
        except Exception as e:
            self.status.config(text=f"Erro ao limpar: {e}", fg="#FF3333")

    def run_engine(self):
        from core.speech_to_text import listen, adjust_noise
        from core.translate import translate
        from core.tts import speak
        from core.osc import send_chat
        from core.beep import beep_start, beep_done

        adjust_noise(self.mic_index)

        while self.running:
            try:
                current_from = LANGS[self.from_lang.get()]
            except KeyError:
                current_from = "pt"

            text = listen(self.mic_index, current_from)

            if not self.running:
                break

            if text:
                try:
                    current_to = LANGS[self.to_lang.get()]
                except KeyError:
                    current_to = "en"

                current_pitch = self.pitch_scale.get()

                # Beeps de feedback (só no headset, nunca no VB-Cable)
                if self.beep_var.get():
                    threading.Thread(target=beep_start, daemon=True).start()
                    threading.Thread(target=beep_done, daemon=True).start()

                # Mesmo idioma → sem tradução
                lang_from_code = current_from if current_from != "auto" else None
                same_lang = (lang_from_code == current_to)

                if same_lang:
                    print("Você:", text)
                    print("(Sem tradução - mesmo idioma)")
                    if self.chatbox_var.get():
                        send_chat(text)
                    if self.tts_var.get():
                        speak(text, current_to, current_pitch)
                else:
                    translated = translate(text, current_to)
                    print("Você:", text)
                    print("Traduzido:", translated)

                    if self.chatbox_var.get():
                        if self.dual_lang_var.get():
                            send_chat(f"({text}) → {translated}")
                        else:
                            send_chat(translated)
                    if self.tts_var.get():
                        speak(translated, current_to, current_pitch)


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()