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
        self.root.title("VRChat Translator MAX PRO")
        self.root.geometry("900x650")  # 🔥 maior

        self.running = False

        devices = sd.query_devices()
        settings = load_settings()

        # 🎤 MIC (MAIOR + VISÍVEL)
        tk.Label(root, text="Microfone", font=("Arial", 12, "bold")).pack()

        self.inputs = [
            (i, d["name"])
            for i, d in enumerate(devices)
            if d["max_input_channels"] > 0
        ]

        self.mic = ttk.Combobox(root, width=80)  # 🔥 maior
        self.mic["values"] = [f"{i} - {n}" for i, n in self.inputs]
        
        # Selecionar mic salvo ou primeiro disponível
        default_mic_idx = 0
        if "mic" in settings:
            for idx, (_, name) in enumerate(self.inputs):
                if name == settings["mic"]:
                    default_mic_idx = idx
                    break
        if self.inputs:
            self.mic.current(default_mic_idx)
        self.mic.pack(pady=5)

        # 🔊 OUTPUT
        tk.Label(root, text="Saída (VB-Cable)", font=("Arial", 12, "bold")).pack()

        self.outputs = [
            (i, d["name"])
            for i, d in enumerate(devices)
            if d["max_output_channels"] > 0
        ]

        self.out = ttk.Combobox(root, width=80)
        self.out["values"] = [f"{i} - {n}" for i, n in self.outputs]
        
        # Selecionar saída salva ou primeira disponível
        default_out_idx = 0
        if "out" in settings:
            for idx, (_, name) in enumerate(self.outputs):
                if name == settings["out"]:
                    default_out_idx = idx
                    break
        if self.outputs:
            self.out.current(default_out_idx)
        self.out.pack(pady=5)

        # 🌍 FROM LANG
        tk.Label(root, text="Idioma origem").pack()

        from_langs_list = list(LANGS.keys())
        self.from_lang = ttk.Combobox(root, values=from_langs_list, width=40)
        
        default_from_idx = 1 # padrão Português (BR)
        if "from_lang" in settings and settings["from_lang"] in from_langs_list:
            default_from_idx = from_langs_list.index(settings["from_lang"])
        self.from_lang.current(default_from_idx)
        self.from_lang.pack()

        # 🌍 TO LANG
        tk.Label(root, text="Idioma destino").pack()

        to_langs_list = [k for k in LANGS.keys() if k != "Auto Detect"]
        self.to_lang = ttk.Combobox(root, values=to_langs_list, width=40)
        
        default_to_idx = 0 # padrão Inglês (US)
        if "to_lang" in settings and settings["to_lang"] in to_langs_list:
            default_to_idx = to_langs_list.index(settings["to_lang"])
        self.to_lang.current(default_to_idx)
        self.to_lang.pack()

        # 🎙 VOZ
        tk.Label(root, text="Voz (automática por idioma)").pack()

        self.voice_label = tk.Label(root, text="Auto (baseado no idioma)")
        self.voice_label.pack()

        # ▶ START
        self.btn_start = tk.Button(root, text="START", command=self.toggle_service, height=2, width=15)
        self.btn_start.pack(pady=15)

        self.status = tk.Label(root, text="Parado", font=("Arial", 12))
        self.status.pack()

    def toggle_service(self):
        if not self.running:
            try:
                mic_index = int(self.mic.get().split(" - ")[0])
                out_index = int(self.out.get().split(" - ")[0])
            except (IndexError, ValueError, AttributeError):
                self.status.config(text="Erro: Selecione microfone e saída!")
                return

            engine.set_output_index(out_index)
            self.mic_index = mic_index

            # Salvar as últimas configurações selecionadas
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
                "to_lang": self.to_lang.get()
            })

            self.status.config(text="Rodando...")
            self.btn_start.config(text="STOP", bg="#ff4d4d", fg="white")
            self.mic.config(state="disabled")
            self.out.config(state="disabled")
            
            self.running = True
            threading.Thread(target=self.run_engine, daemon=True).start()
        else:
            self.running = False
            self.status.config(text="Parado")
            self.btn_start.config(text="START", bg="SystemButtonFace", fg="black")
            self.mic.config(state="normal")
            self.out.config(state="normal")

    def run_engine(self):
        from core.speech_to_text import listen, adjust_noise
        from core.translate import translate
        from core.tts import speak
        from core.osc import send_chat

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

                translated = translate(text, current_to)

                print("Você:", text)
                print("Traduzido:", translated)

                send_chat(f"({text}) → {translated}")

                speak(translated, current_to)


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()