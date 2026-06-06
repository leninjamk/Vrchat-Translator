import tkinter as tk
from tkinter import ttk
import threading
import sounddevice as sd
import sys, os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.singleton import engine
from core.languages import LANGS
from core.voices import VOICES


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("VRChat Translator MAX PRO")
        self.root.geometry("900x650")  # 🔥 maior

        self.running = False

        devices = sd.query_devices()

        # 🎤 MIC (MAIOR + VISÍVEL)
        tk.Label(root, text="Microfone", font=("Arial", 12, "bold")).pack()

        self.inputs = [
            (i, d["name"])
            for i, d in enumerate(devices)
            if d["max_input_channels"] > 0
        ]

        self.mic = ttk.Combobox(root, width=80)  # 🔥 maior
        self.mic["values"] = [f"{i} - {n}" for i, n in self.inputs]
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
        self.out.pack(pady=5)

        # 🌍 FROM LANG
        tk.Label(root, text="Idioma origem").pack()

        self.from_lang = ttk.Combobox(root, values=list(LANGS.keys()), width=40)
        self.from_lang.current(1)
        self.from_lang.pack()

        # 🌍 TO LANG
        tk.Label(root, text="Idioma destino").pack()

        self.to_lang = ttk.Combobox(root, values=list(LANGS.keys()), width=40)
        self.to_lang.current(0)
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
            # Obtém os idiomas dinamicamente a cada loop para responder às alterações na UI
            try:
                current_from = LANGS[self.from_lang.get()]
                current_to = LANGS[self.to_lang.get()]
            except KeyError:
                current_from = "pt"
                current_to = "en"

            text = listen(self.mic_index, current_from)

            if not self.running:
                break

            if text:
                translated = translate(text, current_to)

                print("Você:", text)
                print("Traduzido:", translated)

                send_chat(f"({text}) → {translated}")

                speak(translated, current_to)


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()