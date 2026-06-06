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
        tk.Button(root, text="START", command=self.start, height=2).pack(pady=15)

        self.status = tk.Label(root, text="Parado", font=("Arial", 12))
        self.status.pack()

    def start(self):
        mic_index = int(self.mic.get().split(" - ")[0])
        out_index = int(self.out.get().split(" - ")[0])

        engine.set_output_index(out_index)

        self.mic_index = mic_index

        self.lang_from = LANGS[self.from_lang.get()]
        self.lang_to = LANGS[self.to_lang.get()]

        self.status.config(text="Rodando...")
        self.running = True

        threading.Thread(target=self.run_engine, daemon=True).start()

    def run_engine(self):
        from core.speech_to_text import listen
        from core.translate import translate
        from core.tts import speak
        from core.osc import send_chat

        while self.running:
            text = listen(self.mic_index)

            if text:
                translated = translate(text, self.lang_to)

                print("Você:", text)
                print("Traduzido:", translated)

                send_chat(f"({text}) → {translated}")

                speak(translated, self.lang_to)


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()