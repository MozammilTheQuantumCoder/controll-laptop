import socket
import threading
import pickle
import zlib
from PIL import Image, ImageTk
import io
import tkinter as tk

SERVER_IP = '127.0.0.1'  # replace with your actual server IP
PORT_SCREEN = 9999
PASSWORD = "mysecret123"

client_screen = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client_screen.connect((SERVER_IP, PORT_SCREEN))

# Authentication
if client_screen.recv(1024) == b"PASSWORD:":
    client_screen.sendall(PASSWORD.encode())
    if client_screen.recv(1024) != b"ACCESS GRANTED":
        print("Access denied.")
        exit()

# Get server's resolution
server_resolution = pickle.loads(client_screen.recv(4096))
original_width = server_resolution['width']
original_height = server_resolution['height']

# Tkinter setup
root = tk.Tk()
root.title("Remote Viewer")

# Choose desired scale (e.g. 0.6 = 60% of real screen)
SCALE = 0.6
canvas_width = int(original_width * SCALE)
canvas_height = int(original_height * SCALE)

canvas = tk.Canvas(root, width=canvas_width, height=canvas_height)
canvas.pack()
img_on_canvas = None  # image reference

def receive_screen():
    global img_on_canvas
    while True:
        try:
            size_bytes = client_screen.recv(4)
            if not size_bytes:
                break
            frame_len = int.from_bytes(size_bytes, 'big')

            data = b''
            while len(data) < frame_len:
                packet = client_screen.recv(min(4096, frame_len - len(data)))
                if not packet:
                    return
                data += packet

            frame = zlib.decompress(data)
            image = Image.open(io.BytesIO(frame))

            image = image.resize((canvas_width, canvas_height))
            image_tk = ImageTk.PhotoImage(image)

            if img_on_canvas is None:
                img_on_canvas = canvas.create_image(0, 0, anchor='nw', image=image_tk)
            else:
                canvas.itemconfig(img_on_canvas, image=image_tk)

            canvas.image = image_tk  # avoid garbage collection
        except Exception as e:
            print("Screen error:", e)
            break

def send_input(cmd):
    try:
        payload = zlib.compress(pickle.dumps(cmd))
        client_screen.sendall(payload)
    except Exception as e:
        print("Send input error:", e)

def mouse_move(event):
    scale_x = original_width / canvas.winfo_width()
    scale_y = original_height / canvas.winfo_height()
    send_input({'type': 'move', 'x': int(event.x * scale_x), 'y': int(event.y * scale_y)})

def mouse_click(event):
    send_input({'type': 'click'})

def key_press(event):
    send_input({'type': 'keypress', 'key': event.keysym})

canvas.bind("<Motion>", mouse_move)
canvas.bind("<Button-1>", mouse_click)
root.bind("<Key>", key_press)

threading.Thread(target=receive_screen, daemon=True).start()

root.mainloop()
