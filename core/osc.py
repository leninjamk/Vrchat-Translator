from pythonosc import udp_client

client = udp_client.SimpleUDPClient("127.0.0.1", 9000)

def send_chat(msg):
    client.send_message("/chatbox/input", [msg, True])