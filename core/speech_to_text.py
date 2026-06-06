import speech_recognition as sr

r = sr.Recognizer()

r.dynamic_energy_threshold = False
r.energy_threshold = 200
r.pause_threshold = 1.0


def adjust_noise(mic_index):
    try:
        with sr.Microphone(device_index=mic_index) as source:
            print("🔊 Calibrando ruído ambiente...")
            r.adjust_for_ambient_noise(source, duration=0.8)
            # Garante que o limiar nunca fique excessivamente alto e insensível
            if r.energy_threshold > 400:
                r.energy_threshold = 300
            elif r.energy_threshold < 100:
                r.energy_threshold = 150
            print(f"✔️ Calibração concluída! Limiar: {r.energy_threshold}")
    except Exception as e:
        print("❌ Erro ao calibrar ruído:", e)


def listen(mic_index, language="pt-BR"):
    try:
        with sr.Microphone(device_index=mic_index) as source:
            # timeout=2 garante que se ninguém falar nada por 2 segundos,
            # a função libera o microfone permitindo que a thread verifique self.running
            audio = r.listen(source, timeout=2.0, phrase_time_limit=13)

        try:
            lang = language if language and language != "auto" else "pt-BR"
            text = r.recognize_google(audio, language=lang)
            return text
        except Exception:
            return ""

    except sr.WaitTimeoutError:
        # Silêncio no timeout, ignora de forma limpa e retorna vazio
        return ""
    except Exception as e:
        print("❌ mic error:", e)
        return ""