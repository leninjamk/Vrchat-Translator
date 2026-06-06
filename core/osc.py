from pythonosc import udp_client

try:
    from config import OSC_IP, OSC_PORT
except ImportError:
    OSC_IP = "127.0.0.1"
    OSC_PORT = 9000

client = udp_client.SimpleUDPClient(OSC_IP, OSC_PORT)

def send_chat(msg):
    client.send_message("/chatbox/input", [msg, True])