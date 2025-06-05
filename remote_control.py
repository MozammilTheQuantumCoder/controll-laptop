import socket
import threading
import zlib
import pickle
import pyautogui
import io
from PIL import Image
import mss
import pyaudio

HOST = '0.0.0.0'
PORT_SCREEN = 9999
PORT_AUDIO = 9998

PASSWORD = "mysecret123"  # Change your password here

# Setup server sockets for screen/input and audio separately
server_screen = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_screen.bind((HOST, PORT_SCREEN))
server_screen.listen(1)

server_audio = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_audio.bind((HOST, PORT_AUDIO))
server_audio.listen(1)

print("Waiting for screen/input connection...")
conn_screen, addr_screen = server_screen.accept()
print(f"Screen/Input connected by {addr_screen}")

# AUTHENTICATION
conn_screen.sendall(b"PASSWORD:")
client_password = conn_screen.recv(1024).decode()
if client_password != PASSWORD:
    conn_screen.sendall(b"ACCESS DENIED")
    conn_screen.close()
    print("Wrong password, disconnected:", addr_screen)
    exit()
else:
    conn_screen.sendall(b"ACCESS GRANTED")
    print("Client authenticated:", addr_screen)

print("Waiting for audio connection...")
conn_audio, addr_audio = server_audio.accept()
print(f"Audio connected by {addr_audio}")

screen_width, screen_height = pyautogui.size()
conn_screen.sendall(pickle.dumps({'width': screen_width, 'height': screen_height}))

# Audio setup
p = pyaudio.PyAudio()
audio_stream = p.open(format=pyaudio.paInt16, channels=1, rate=44100, input=True, frames_per_buffer=1024)

def handle_input():
    while True:
        try:
            data = conn_screen.recv(4096)
            if not data:
                break
            command = pickle.loads(zlib.decompress(data))
            if command['type'] == 'move':
                pyautogui.moveTo(command['x'], command['y'])
            elif command['type'] == 'click':
                pyautogui.click()
            elif command['type'] == 'keypress':
                try:
                    pyautogui.press(command['key'])
                except Exception as e:
                    print("Failed to press key:", command['key'], e)
        except Exception as e:
            print("Input error:", e)
            break

def stream_screen():
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        while True:
            img = sct.grab(monitor)
            img_pil = Image.frombytes("RGB", img.size, img.rgb)
            buf = io.BytesIO()
            img_pil.save(buf, format='JPEG', quality=50, optimize=True)
            compressed = zlib.compress(buf.getvalue(), level=6)
            try:
                conn_screen.sendall(len(compressed).to_bytes(4, 'big') + compressed)
            except Exception as e:
                print("Send screen error:", e)
                break

def stream_audio():
    while True:
        try:
            data = audio_stream.read(1024)
            compressed = zlib.compress(data)
            conn_audio.sendall(len(compressed).to_bytes(4, 'big') + compressed)
        except Exception as e:
            print("Send audio error:", e)
            break

threading.Thread(target=handle_input, daemon=True).start()
threading.Thread(target=stream_screen, daemon=True).start()
threading.Thread(target=stream_audio, daemon=True).start()

try:
    while True:
        pass
except KeyboardInterrupt:
    conn_screen.close()
    conn_audio.close()
    server_screen.close()
    server_audio.close()
    audio_stream.stop_stream()
    audio_stream.close()
    p.terminate()
