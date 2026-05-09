"""Raw cluster handshake diagnostic — shows exactly what the cluster sends."""
import socket
import time

HOST = "ve7cc.net"
PORT = 23
CALLSIGN = "N6YU"

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(5.0)
sock.connect((HOST, PORT))
print(f"Connected to {HOST}:{PORT}\n--- RAW OUTPUT ---")

# Read whatever the cluster sends first
buf = ""
deadline = time.monotonic() + 5.0
while time.monotonic() < deadline:
    try:
        chunk = sock.recv(1024).decode(errors="replace")
        if not chunk:
            break
        buf += chunk
        print(repr(chunk))
    except socket.timeout:
        break

print("\n--- SENDING CALLSIGN ---")
sock.sendall((CALLSIGN + "\r\n").encode())
time.sleep(3)

print("--- POST-LOGIN OUTPUT ---")
deadline = time.monotonic() + 5.0
while time.monotonic() < deadline:
    try:
        chunk = sock.recv(1024).decode(errors="replace")
        if not chunk:
            break
        print(repr(chunk))
    except socket.timeout:
        break

sock.close()
