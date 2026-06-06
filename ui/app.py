import tkinter as tk
from tkinter import ttk
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


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("VRChat Speech Assistant")
        self.root.geometry("420x750")
        self.root.resizable(False, False)
        self.root.configure(bg="#181818")

        self.running = False

        devices = sd.query_devices()
        settings = load_settings()

        # Estilo dos Comboboxes (Dark Theme)
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TCombobox", 
                        fieldbackground="#252525", 
                        background="#252525", 
                        foreground="#FFFFFF",
                        bordercolor="#333333",
                        darkcolor="#252525",
                        lightcolor="#252525",
                        arrowcolor="#FFFFFF")
        
        # Cores dropdown listbox do combobox
        root.option_add("*TCombobox*Listbox.background", "#252525")
        root.option_add("*TCombobox*Listbox.foreground", "#FFFFFF")
        root.option_add("*TCombobox*Listbox.selectBackground", "#4C8BF5")
        root.option_add("*TCombobox*Listbox.selectForeground", "#FFFFFF")
        root.option_add("*TCombobox*Listbox.borderWidth", "0")

        # Banner do Título
        title_frame = tk.Frame(root, bg="#181818")
        title_frame.pack(pady=(20, 5))
        
        tk.Label(title_frame, text="VRChat Speech", font=("Segoe UI", 20, "bold"), bg="#181818", fg="#FFFFFF").pack()
        tk.Label(title_frame, text="TRANSLATOR MAX PRO", font=("Segoe UI", 10, "bold"), bg="#181818", fg="#4C8BF5").pack()

        # Dica / Instrução
        tk.Label(root, text="Fale claramente e evite fontes de ruído de fundo.", 
                 font=("Segoe UI", 9, "italic"), bg="#181818", fg="#888888").pack(pady=(0, 15))

        # Configurações de opções de fonte comum
        lbl_opts = {"bg": "#181818", "fg": "#CCCCCC", "font": ("Segoe UI", 9, "bold")}

        # 🎤 MICROFONE (INPUT)
        tk.Label(root, text="Dispositivo de entrada (Microfone):", **lbl_opts).pack(anchor="w", padx=30, pady=(5, 2))
        self.inputs = [
            (i, d["name"])
            for i, d in enumerate(devices)
            if d["max_input_channels"] > 0
        ]
        self.mic = ttk.Combobox(root, width=45)
        self.mic["values"] = [f"{i} - {n}" for i, n in self.inputs]
        
        default_mic_idx = 0
        if "mic" in settings:
            for idx, (_, name) in enumerate(self.inputs):
                if name == settings["mic"]:
                    default_mic_idx = idx
                    break
        if self.inputs:
            self.mic.current(default_mic_idx)
        self.mic.pack(padx=30, fill="x")

        # 🌍 IDIOMA ORIGEM
        tk.Label(root, text="Idioma de origem:", **lbl_opts).pack(anchor="w", padx=30, pady=(12, 2))
        from_langs_list = list(LANGS.keys())
        self.from_lang = ttk.Combobox(root, width=45, values=from_langs_list)
        
        default_from_idx = 1
        if "from_lang" in settings and settings["from_lang"] in from_langs_list:
            default_from_idx = from_langs_list.index(settings["from_lang"])
        self.from_lang.current(default_from_idx)
        self.from_lang.pack(padx=30, fill="x")

        # 🌍 IDIOMA DESTINO
        tk.Label(root, text="Idioma de destino:", **lbl_opts).pack(anchor="w", padx=30, pady=(12, 2))
        to_langs_list = [k for k in LANGS.keys() if k != "Auto Detect"]
        self.to_lang = ttk.Combobox(root, width=45, values=to_langs_list)
        
        default_to_idx = 0
        if "to_lang" in settings and settings["to_lang"] in to_langs_list:
            default_to_idx = to_langs_list.index(settings["to_lang"])
        self.to_lang.current(default_to_idx)
        self.to_lang.pack(padx=30, fill="x")

        # 🎛️ VOICE PITCH SLIDER
        tk.Label(root, text="Voice Pitch (Tom de Voz):", **lbl_opts).pack(anchor="w", padx=30, pady=(15, 2))
        slider_frame = tk.Frame(root, bg="#181818")
        slider_frame.pack(fill="x", padx=30)
        
        tk.Label(slider_frame, text="Grave", bg="#181818", fg="#777777", font=("Segoe UI", 8, "bold")).pack(side="left")
        
        self.pitch_scale = tk.Scale(slider_frame, from_=-50, to=50, orient=tk.HORIZONTAL,
                                    bg="#181818", fg="#FFFFFF", highlightthickness=0,
                                    troughcolor="#252525", activebackground="#4C8BF5",
                                    showvalue=True, bd=0)
        self.pitch_scale.set(settings.get("pitch", 0))
        self.pitch_scale.pack(side="left", fill="x", expand=True, padx=8)
        
        tk.Label(slider_frame, text="Agudo", bg="#181818", fg="#777777", font=("Segoe UI", 8, "bold")).pack(side="right")

        # 🔊 SAÍDA DE ÁUDIO (OUTPUT)
        tk.Label(root, text="Dispositivo de saída (VB-Cable / Headset):", **lbl_opts).pack(anchor="w", padx=30, pady=(12, 2))
        self.outputs = [
            (i, d["name"])
            for i, d in enumerate(devices)
            if d["max_output_channels"] > 0
        ]
        self.out = ttk.Combobox(root, width=45)
        self.out["values"] = [f"{i} - {n}" for i, n in self.outputs]
        
        default_out_idx = 0
        if "out" in settings:
            for idx, (_, name) in enumerate(self.outputs):
                if name == settings["out"]:
                    default_out_idx = idx
                    break
        if self.outputs:
            self.out.current(default_out_idx)
        self.out.pack(padx=30, fill="x")

        # Espaçador
        tk.Frame(root, height=10, bg="#181818").pack()

        # ▶ BOTÃO START LISTENING
        self.btn_start = tk.Button(root, text="START LISTENING", command=self.toggle_service,
                                   bg="#252525", fg="#FFFFFF", font=("Segoe UI", 11, "bold"),
                                   activebackground="#333333", activeforeground="#FFFFFF",
                                   bd=0, relief="flat", height=2, cursor="hand2")
        self.btn_start.pack(padx=30, fill="x", pady=(15, 8))

        # 🧹 BOTÃO CLEAR CHATBOX TEXT
        self.btn_clear = tk.Button(root, text="Clear Chatbox text", command=self.clear_chatbox,
                                   bg="#1F1F1F", fg="#888888", font=("Segoe UI", 9),
                                   activebackground="#252525", activeforeground="#CCCCCC",
                                   bd=0, relief="flat", height=1, cursor="hand2")
        self.btn_clear.pack(padx=30, fill="x", pady=(0, 6))

        # 🔔 CHECKBOX BEEP
        self.beep_var = tk.BooleanVar(value=settings.get("beep", True))
        beep_frame = tk.Frame(root, bg="#181818")
        beep_frame.pack(padx=30, fill="x", pady=(0, 6))
        self.beep_check = tk.Checkbutton(
            beep_frame, text="✔ Som de aviso ao reconhecer fala",
            variable=self.beep_var,
            bg="#181818", fg="#888888",
            activebackground="#181818", activeforeground="#CCCCCC",
            selectcolor="#252525",
            font=("Segoe UI", 9), anchor="w", cursor="hand2"
        )
        self.beep_check.pack(side="left")

        # 📝 BARRA DE STATUS
        self.status = tk.Label(root, text="Parado", font=("Segoe UI", 9), bg="#181818", fg="#666666")
        self.status.pack(pady=8)

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
                "mic": mic_name,
                "out": out_name,
                "from_lang": self.from_lang.get(),
                "to_lang": self.to_lang.get(),
                "pitch": self.pitch_scale.get(),
                "beep": self.beep_var.get()
            })

            self.status.config(text="Escutando...", fg="#4C8BF5")
            self.btn_start.config(text="STOP LISTENING", bg="#A31D1D")
            self.mic.config(state="disabled")
            self.out.config(state="disabled")
            
            self.running = True
            threading.Thread(target=self.run_engine, daemon=True).start()
        else:
            self.running = False
            self.status.config(text="Parado", fg="#666666")
            self.btn_start.config(text="START LISTENING", bg="#252525")
            self.mic.config(state="normal")
            self.out.config(state="normal")

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

                # Lê o pitch em tempo real da interface
                current_pitch = self.pitch_scale.get()

                # Beep de aviso: toca ao detectar fala (beep_start) e ao finalizar (beep_done)
                if self.beep_var.get():
                    threading.Thread(target=beep_start, daemon=True).start()
                    threading.Thread(target=beep_done, daemon=True).start()

                # Se o idioma de origem e destino forem iguais, não traduz
                lang_from_code = current_from if current_from != "auto" else None
                same_lang = (lang_from_code == current_to)

                if same_lang:
                    # Mesmo idioma: apenas fala o texto original sem tradução
                    print("Você:", text)
                    print("(Sem tradução - mesmo idioma)")
                    send_chat(text)
                    speak(text, current_to, current_pitch)
                else:
                    translated = translate(text, current_to)

                    print("Você:", text)
                    print("Traduzido:", translated)

                    send_chat(f"({text}) → {translated}")
                    speak(translated, current_to, current_pitch)


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()