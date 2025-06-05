import socket
import zlib
import pickle
import threading
import pygame
import io
from pynput.keyboard import Listener as KeyListener

HOST = '192.168.1.100'  # <-- Change to your server IP
PORT = 9999

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect((HOST, PORT))

# Receive server resolution info
data = b''
while len(data) < 1024:
    packet = client.recv(1024)
    if not packet:
        break
    data += packet
try:
    server_screen_info = pickle.loads(data)
    SERVER_WIDTH = server_screen_info['width']
    SERVER_HEIGHT = server_screen_info['height']
except Exception as e:
    print("Error getting server resolution:", e)
    SERVER_WIDTH, SERVER_HEIGHT = 1920, 1080  # fallback

pygame.init()

# Create window with server resolution ratio but limit max size for display
MAX_WIDTH, MAX_HEIGHT = 1280, 720
scale_w = min(MAX_WIDTH, SERVER_WIDTH)
scale_h = int((scale_w / SERVER_WIDTH) * SERVER_HEIGHT)
screen = pygame.display.set_mode((scale_w, scale_h))
pygame.display.set_caption("Remote Viewer")

def receive_screen():
    while True:
        try:
            raw_len = client.recv(4)
            if not raw_len:
                break
            frame_len = int.from_bytes(raw_len, 'big')
            frame_data = b''
            while len(frame_data) < frame_len:
                packet = client.recv(frame_len - len(frame_data))
                if not packet:
                    break
                frame_data += packet
            image = zlib.decompress(frame_data)
            img = pygame.image.load(io.BytesIO(image))
            img = pygame.transform.scale(img, (scale_w, scale_h))
            screen.blit(img, (0, 0))
            pygame.display.update()
        except Exception as e:
            print("Screen error:", e)
            break

def send_input(command):
    packed = zlib.compress(pickle.dumps(command))
    client.sendall(packed)

from pynput.keyboard import Key

def on_key_press(key):
    try:
        if hasattr(key, 'char') and key.char is not None:
            send_input({'type': 'keypress', 'key': key.char})
        else:
            send_input({'type': 'keypress', 'key': key.name})
    except Exception as e:
        print("Key press send error:", e)

threading.Thread(target=receive_screen, daemon=True).start()
threading.Thread(target=lambda: KeyListener(on_press=on_key_press).run(), daemon=True).start()

while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            client.close()
            pygame.quit()
            exit()
        elif event.type == pygame.MOUSEMOTION:
            x, y = pygame.mouse.get_pos()
            scaled_x = int((x / scale_w) * SERVER_WIDTH)
            scaled_y = int((y / scale_h) * SERVER_HEIGHT)
            send_input({'type': 'move', 'x': scaled_x, 'y': scaled_y})
        elif event.type == pygame.MOUSEBUTTONDOWN:
            send_input({'type': 'click'})
