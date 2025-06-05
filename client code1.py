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
PASSWORD = "mysecret123"

# --- Connect to Screen/Input Server ---
client_screen = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client_screen.connect((SERVER_IP, PORT_SCREEN))

# --- Authenticate ---
msg = client_screen.recv(1024).decode()
if msg == "PASSWORD:":
    client_screen.sendall(PASSWORD.encode())
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

# --- Receive server screen resolution ---
screen_info = pickle.loads(client_screen.recv(1024))
server_w, server_h = screen_info['width'], screen_info['height']

# --- Initialize Pygame and get client display size ---
pygame.init()
info = pygame.display.Info()
client_w, client_h = info.current_w, info.current_h

# --- Create window (resizable initially, toggle fullscreen with F11) ---
window = pygame.display.set_mode((client_w, client_h), pygame.RESIZABLE)
pygame.display.set_caption("Remote Desktop Viewer")

# --- Calculate scaling ratios ---
def get_scale():
    w, h = window.get_size()
    return server_w / w, server_h / h

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
            data = b''
            while len(data) < length:
                packet = client_audio.recv(length - len(data))
                if not packet: return
                data += packet
            audio = zlib.decompress(data)
            audio_stream.write(audio)
        except Exception as e:
            print("Audio error:", e)
            break

def send_input(event):
    scale_x, scale_y = get_scale()
    if event.type == pygame.MOUSEMOTION:
        x, y = pygame.mouse.get_pos()
        command = {'type': 'move', 'x': int(x * scale_x), 'y': int(y * scale_y)}
    elif event.type == pygame.MOUSEBUTTONDOWN:
        command = {'type': 'click'}
    elif event.type == pygame.KEYDOWN:
        if event.key == pygame.K_F11:
            pygame.display.toggle_fullscreen()
            return
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
                if not packet: return
                data += packet
            img_data = zlib.decompress(data)
            img = pygame.image.load(io.BytesIO(img_data)).convert()
            window_w, window_h = window.get_size()
            img_scaled = pygame.transform.scale(img, (window_w, window_h))
            window.blit(img_scaled, (0, 0))
            pygame.display.flip()
        except Exception as e:
            print("Screen error:", e)
            break

# --- Start Threads ---
threading.Thread(target=receive_audio, daemon=True).start()
threading.Thread(target=receive_screen, daemon=True).start()

# --- Main Loop ---
while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            client_screen.close()
            client_audio.close()
            pygame.quit()
            exit()
        send_input(event)
