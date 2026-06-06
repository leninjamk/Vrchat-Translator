import numpy as np
import sounddevice as sd


def _generate_tone(freq_start, freq_end, duration=0.25, volume=0.3, sample_rate=44100):
    """
    Gera um tom com frequência variando de freq_start a freq_end,
    com envelope suave de fade-in e fade-out.
    Sempre toca no dispositivo PADRÃO do sistema (fone/headset do usuário),
    nunca no VB-Cable ou saída do jogo.
    """
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)

    freq = np.linspace(freq_start, freq_end, len(t))
    phase = np.cumsum(2 * np.pi * freq / sample_rate)
    wave = np.sin(phase)

    fade_in = int(sample_rate * 0.02)
    fade_out = int(sample_rate * 0.12)
    envelope = np.ones(len(t))
    envelope[:fade_in] = np.linspace(0, 1, fade_in)
    envelope[-fade_out:] = np.linspace(1, 0, fade_out)

    return (wave * envelope * volume).astype(np.float32), sample_rate


def beep_start():
    """
    Toca um tom DESCENDENTE curto (agudo → grave) para indicar:
    'Estou escutando agora, pode falar!'
    Toca SEMPRE no dispositivo padrão do sistema (seu fone/headset),
    NUNCA no VB-Cable ou saída do VRChat.
    """
    try:
        wave, sr = _generate_tone(freq_start=800, freq_end=400, duration=0.2, volume=0.25)
        sd.play(wave, sr, device=None)  # None = saída padrão do sistema (headset)
        sd.wait()
    except Exception as e:
        print("❌ Beep start error:", e)


def beep_done():
    """
    Toca um tom ASCENDENTE (grave → agudo) para indicar:
    'Fala reconhecida e traduzida!'
    Toca SEMPRE no dispositivo padrão do sistema (seu fone/headset),
    NUNCA no VB-Cable ou saída do VRChat.
    """
    try:
        wave, sr = _generate_tone(freq_start=300, freq_end=900, duration=0.35, volume=0.35)
        sd.play(wave, sr, device=None)  # None = saída padrão do sistema (headset)
        sd.wait()
    except Exception as e:
        print("❌ Beep done error:", e)
