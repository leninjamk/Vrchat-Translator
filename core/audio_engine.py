import sounddevice as sd
import soundfile as sf

class AudioEngine:
    def __init__(self):
        self.output_device = None

    def set_output_index(self, index):
        self.output_device = index
        print(f"🎧 OUTPUT fixado: {index}")

    def play(self, file):
        if self.output_device is None:
            print("❌ sem saída definida")
            return

        data, sr = sf.read(file)

        sd.play(data, sr, device=self.output_device)
        sd.wait()