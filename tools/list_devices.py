import sounddevice as sd

devices = sd.query_devices()

print("\n===== DISPOSITIVOS DE ÁUDIO =====\n")

for i, d in enumerate(devices):
    io = []

    if d["max_input_channels"] > 0:
        io.append("MIC")

    if d["max_output_channels"] > 0:
        io.append("OUT")

    print(f"{i} - {d['name']} [{', '.join(io)}]")
