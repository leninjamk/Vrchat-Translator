from core.audio_engine import AudioEngine

# engine: usado pra TTS da MINHA fala (ex: pode apontar pro VB-Cable, pra
# outros jogadores ouvirem a traducao). received_tts_engine: usado pra TTS da
# fala RECEBIDA (traducao do que os outros falam) — precisa de um dispositivo
# separado (fone/headset/VR real), NUNCA o cabo virtual, senao: (1) eu mesmo
# nunca ouço, e (2) o VRChat manda essa fala de volta pros outros como se
# fosse minha, o que nao faz sentido pra uma traducao do que ELES disseram.
engine = AudioEngine()
received_tts_engine = AudioEngine()