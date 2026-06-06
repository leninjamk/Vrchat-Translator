import speech_recognition as sr

r = sr.Recognizer()

r.dynamic_energy_threshold = True
r.energy_threshold = 300
r.pause_threshold = 0.8


def listen(mic_index, language="pt-BR"):
    try:
        with sr.Microphone(device_index=mic_index) as source:
            r.adjust_for_ambient_noise(source, duration=0.5)

            audio = r.listen(source, phrase_time_limit=8)

        try:
            lang = language if language and language != "auto" else "pt-BR"
            text = r.recognize_google(audio, language=lang)
            return text

        except:
            return ""

    except Exception as e:
        print("❌ mic error:", e)
        return ""