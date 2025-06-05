import socket
import zlib
import pickle
import threading
import pygame
import io
from pynput.keyboard import Listener as KeyListener
import pyaudio

HOST = '192.168.1.100'  # Change this to your server IP
PORT_SCREEN = 9999
PORT_AUDIO = 9998

client_screen = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client_screen.connect((HOST, PORT_SCREEN))

# AUTHENTICATION
response = client_screen.recv(1024)
if response == b"PASSWORD:":
    pwd = input("Enter password: ")
    client_screen.sendall(pwd.encode())
    reply = client_screen.recv(1024)
    if reply != b"ACCESS GRANTED":
        print("Wrong password, closing.")
        client_screen.close()
        exit()
else:
    print("Unexpected response:", response)
    client_screen.close()
    exit()

client_audio = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client_audio.connect((HOST, PORT_AUDIO))

# Receive server screen resolution info
data = b''
while len(data) < 1024:
    packet = client_screen.recv(1024)
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

# Start window at smaller size, resizable
init_width, init_height = 1280, int((1280 / SERVER_WIDTH) * SERVER_HEIGHT)
screen = pygame.display.set_mode((init_width, init_height), pygame.RESIZABLE)
pygame.display.set_caption("Remote Viewer")

current_width, current_height = init_width, init_height

def receive_screen():
    global current_width, current_height
    while True:
        try:
            raw_len = client_screen.recv(4)
            if not raw_len:
                break
            frame_len = int.from_bytes(raw_len, 'big')
            frame_data = b''
            while len(frame_data) < frame_len:
                packet = client_screen.recv(frame_len - len(frame_data))
                if not packet:
                    break
                frame_data += packet
            image = zlib.decompress(frame_data)
            img = pygame.image.load(io.BytesIO(image))
            img = pygame.transform.scale(img, (current_width, current_height))
            screen.blit(img, (0, 0))
            pygame.display.update()
        except Exception as e:
            print("Screen error:", e)
            break

def send_input(command):
    packed = zlib.compress(pickle.dumps(command))
    client_screen.sendall(packed)

from pynput.keyboard import Key

def on_key_press(key):
    try:
        if hasattr(key, 'char') and key.char is not None:
            send_input({'type': 'keypress', 'key': key.char})
        else:
            send_input({'type': 'keypress', 'key': key.name})
    except Exception as e:
        print("Key press send error:", e)

# Audio playback setup
p = pyaudio.PyAudio()
stream = p.open(format=pyaudio.paInt16, channels=1, rate=44100, output=True, frames_per_buffer=1024)

def receive_audio():
    while True:
        try:
            raw_len = client_audio.recv(4)
            if not raw_len:
                break
            length = int.from_bytes(raw_len, 'big')
            data = b''
            while len(data) < length:
                packet = client_audio.recv(length - len(data))
                if not packet:
                    break
                data += packet
            audio_data = zlib.decompress(data)
            stream.write(audio_data)
        except Exception as e:
            print("Audio error:", e)
            break

threading.Thread(target=receive_screen, daemon=True).start()
threading.Thread(target=receive_audio, daemon=True).start()
threading.Thread(target=lambda: KeyListener(on_press=on_key_press).run(), daemon=True).start()

while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            client_screen.close()
            client_audio.close()
            pygame.quit()
            exit()
        elif event.type == pygame.VIDEORESIZE:
            current_width, current_height = event.w, event.h
            screen = pygame.display.set_mode((current_width, current_height), pygame.RESIZABLE)
        elif event.type == pygame.MOUSEMOTION:
            x, y = pygame.mouse.get_pos()
            scaled_x = int((x / current_width) * SERVER_WIDTH)
            scaled_y = int((y / current_height) * SERVER_HEIGHT)
            send_input({'type': 'move', 'x': scaled_x, 'y': scaled_y})
        elif event.type == pygame.MOUSEBUTTONDOWN:
            send_input({'type': 'click'})