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
PASSWORD = "mysecret123"

# Setup sockets
server_screen = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_screen.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_screen.bind((HOST, PORT_SCREEN))
server_screen.listen(1)

server_audio = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_audio.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_audio.bind((HOST, PORT_AUDIO))
server_audio.listen(1)

print("[SERVER] Waiting for screen/input connection...")
conn_screen, addr = server_screen.accept()
print("[SERVER] Screen/Input connected from", addr)

# AUTHENTICATION
conn_screen.sendall(b"PASSWORD:")
if conn_screen.recv(1024).decode() != PASSWORD:
    conn_screen.sendall(b"ACCESS DENIED")
    conn_screen.close()
    print("[SERVER] Client failed authentication.")
    exit()
else:
    conn_screen.sendall(b"ACCESS GRANTED")
    print("[SERVER] Client authenticated.")

print("[SERVER] Waiting for audio connection...")
conn_audio, addr_audio = server_audio.accept()
print("[SERVER] Audio connected from", addr_audio)

# Send screen size
screen_w, screen_h = pyautogui.size()
conn_screen.sendall(pickle.dumps({'width': screen_w, 'height': screen_h}))

# Audio stream setup
p = pyaudio.PyAudio()
audio_stream = p.open(format=pyaudio.paInt16, channels=1, rate=44100, input=True, frames_per_buffer=1024)

def handle_input():
    while True:
        try:
            data = conn_screen.recv(4096)
            if not data:
                print("[SERVER] Input stream ended.")
                break
            cmd = pickle.loads(zlib.decompress(data))
            if cmd['type'] == 'move':
                pyautogui.moveTo(cmd['x'], cmd['y'])
            elif cmd['type'] == 'click':
                pyautogui.click()
            elif cmd['type'] == 'keypress':
                try:
                    pyautogui.press(cmd['key'])
                except Exception as e:
                    print("[SERVER] Key press error:", cmd['key'], e)
        except Exception as e:
            print("[SERVER] Input error:", e)
            break

def stream_screen():
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        while True:
            try:
                screenshot = sct.grab(monitor)
                img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)
                # Resize to reduce lag
                img = img.resize((int(img.width * 0.5), int(img.height * 0.5)))
                buf = io.BytesIO()
                img.save(buf, format='JPEG', quality=40)
                compressed = zlib.compress(buf.getvalue(), level=3)
                conn_screen.sendall(len(compressed).to_bytes(4, 'big') + compressed)
            except Exception as e:
                print("[SERVER] Screen stream error:", e)
                break

def stream_audio():
    while True:
        try:
            data = audio_stream.read(1024, exception_on_overflow=False)
            compressed = zlib.compress(data, level=3)
            conn_audio.sendall(len(compressed).to_bytes(4, 'big') + compressed)
        except Exception as e:
            print("[SERVER] Audio stream error:", e)
            break

# Start threads
threading.Thread(target=handle_input, daemon=True).start()
threading.Thread(target=stream_screen, daemon=True).start()
threading.Thread(target=stream_audio, daemon=True).start()

try:
    while True:
        pass
except KeyboardInterrupt:
    print("[SERVER] Shutting down.")
    conn_screen.close()
    conn_audio.close()
    server_screen.close()
    server_audio.close()
    audio_stream.stop_stream()
    audio_stream.close()
    p.terminate()
