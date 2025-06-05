import socket
import zlib
import pickle
import pygame
import io
import threading
import pyaudio

SERVER_IP = 'YOUR_SERVER_IP'  # Replace with your server's IP
PORT_SCREEN = 9999
PORT_AUDIO = 9998

# --- Connect to Screen/Input Server ---
client_screen = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client_screen.connect((SERVER_IP, PORT_SCREEN))

# --- Authenticate ---
msg = client_screen.recv(1024).decode()
if msg == "PASSWORD:":
    client_screen.sendall(input("Password: ").encode())
    response = client_screen.recv(1024).decode()
    if response != "ACCESS GRANTED":
        print("Access denied by server.")
        client_screen.close()
        exit()
    else:
        print("Access granted.")

# --- Connect to Audio Server ---
client_audio = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client_audio.connect((SERVER_IP, PORT_AUDIO))

# --- Receive screen resolution ---
screen_info = pickle.loads(client_screen.recv(1024))
screen_w, screen_h = screen_info['width'], screen_info['height']
window = pygame.display.set_mode((screen_w, screen_h))
pygame.display.set_caption("Remote Screen Viewer")

# --- Audio Playback Setup ---
p = pyaudio.PyAudio()
audio_stream = p.open(format=pyaudio.paInt16, channels=1, rate=44100, output=True, frames_per_buffer=1024)

def receive_audio():
    while True:
        try:
            length_bytes = client_audio.recv(4)
            if not length_bytes:
                break
            length = int.from_bytes(length_bytes, 'big')
            data = client_audio.recv(length)
            audio = zlib.decompress(data)
            audio_stream.write(audio)
        except Exception as e:
            print("Audio error:", e)
            break

def send_input(event):
    if event.type == pygame.MOUSEMOTION:
        x, y = pygame.mouse.get_pos()
        command = {'type': 'move', 'x': x, 'y': y}
    elif event.type == pygame.MOUSEBUTTONDOWN:
        command = {'type': 'click'}
    elif event.type == pygame.KEYDOWN:
        key = pygame.key.name(event.key)
        command = {'type': 'keypress', 'key': key}
    else:
        return
    try:
        client_screen.sendall(zlib.compress(pickle.dumps(command)))
    except Exception as e:
        print("Input send error:", e)

def receive_screen():
    while True:
        try:
            length_bytes = client_screen.recv(4)
            if not length_bytes:
                break
            length = int.from_bytes(length_bytes, 'big')
            data = b''
            while len(data) < length:
                packet = client_screen.recv(length - len(data))
                if not packet:
                    return
                data += packet
            img_data = zlib.decompress(data)
            img = pygame.image.load(io.BytesIO(img_data)).convert()
            window.blit(pygame.transform.scale(img, (screen_w, screen_h)), (0, 0))
            pygame.display.flip()
        except Exception as e:
            print("Screen error:", e)
            break

# --- Start Threads ---
threading.Thread(target=receive_audio, daemon=True).start()
threading.Thread(target=receive_screen, daemon=True).start()

# --- Main Event Loop ---
pygame.init()
while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            client_screen.close()
            client_audio.close()
            pygame.quit()
            exit()
        send_input(event)
