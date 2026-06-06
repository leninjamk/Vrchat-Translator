from core.speech_to_text import listen
from core.translate import translate
from core.tts import speak
from core.osc import send_chat

def start_system(mic_index=None):
    print("🚀 rodando sistema...")

    while True:
        text = listen(mic_index)

        if text:
            translated = translate(text, "en")

            print("Você:", text)
            print("Traduzido:", translated)

            send_chat(f"({text}) → {translated}")
            speak(translated, "en")