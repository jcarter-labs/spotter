"""CC Cluster command diagnostic tool.

Three modes:

  Handshake only (original):
      .venv/bin/python cluster_debug.py

  Interactive — type commands, see raw server responses:
      .venv/bin/python cluster_debug.py --interactive

  Probe — automatically test candidate location/band filter commands:
      .venv/bin/python cluster_debug.py --probe
"""

import argparse
import socket
import sys
import threading
import time

HOST = "ve7cc.net"
PORT = 23
CALLSIGN = "N6YU"
LOGIN_WAIT = 2.5   # seconds after sending callsign before sending commands

# ---------------------------------------------------------------------------
# Candidate commands to probe.  For each entry:
#   (label, command_to_send)
# After every non-SH/FILTER command we automatically send SH/FILTER and
# capture the delta so we can see whether the command registered.
# ---------------------------------------------------------------------------
PROBE_CMDS = [
    # --- baseline ---
    ("Baseline SH/FILTER",               "SH/FILTER"),

    # --- spotter location candidates ---
    ("Spotter: SET/ORIGIN NA",           "SET/ORIGIN NA"),
    ("Spotter: SET/SPOTTER NA",          "SET/SPOTTER NA"),
    ("Spotter: ACCEPT/SPOT by_continent","ACCEPT/SPOT 1 by_continent NA"),
    ("Spotter: SET/SPOT_ORIG_CTY NA",    "SET/SPOT_ORIG_CTY NA"),
    ("Spotter: SET/SPOTORIGCTY NA",      "SET/SPOTORIGCTY NA"),

    # --- DX location candidates ---
    ("DX: ACCEPT/SPOT call_continent",   "ACCEPT/SPOT 1 call_continent EU"),
    ("DX: SET/DXCTY EU",                 "SET/DXCTY EU"),
    ("DX: SET/DX_CTY EU",               "SET/DX_CTY EU"),

    # --- band filter candidates ---
    ("Band: SET/BAND 20",                "SET/BAND 20"),
    ("Band: SET/NOBAND 40",              "SET/NOBAND 40"),
    ("Band: REJECT/SPOT on 40m",         "REJECT/SPOT 1 on 40m"),
    ("Band: SET/FILTER BAND 20",         "SET/FILTER BAND 20"),

    # --- reset ---
    ("Reset: CLEAR/SPOTS ALL",           "CLEAR/SPOTS ALL"),
    ("Final SH/FILTER",                  "SH/FILTER"),
]

PAUSE = 1.5   # seconds between commands in probe mode


# ---------------------------------------------------------------------------
# Shared: connect and login
# ---------------------------------------------------------------------------

def connect_and_login(extra_cmds=()):
    """Return an open, logged-in socket. Sends SET/SKIMMER + any extra_cmds."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(15)
    sock.connect((HOST, PORT))
    sock.settimeout(None)
    sock.sendall((CALLSIGN + "\r\n").encode())
    time.sleep(LOGIN_WAIT)
    sock.sendall(b"SET/SKIMMER\r\n")
    time.sleep(0.5)
    for cmd in extra_cmds:
        sock.sendall((cmd + "\r\n").encode())
        time.sleep(0.3)
    return sock


def read_for(sock, seconds):
    """Collect all data arriving on sock over the next `seconds` seconds."""
    sock.settimeout(seconds)
    buf = []
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            chunk = sock.recv(4096).decode(errors="replace")
            if not chunk:
                break
            buf.append(chunk)
        except socket.timeout:
            break
    sock.settimeout(None)
    return "".join(buf)


# ---------------------------------------------------------------------------
# Mode 1: handshake only
# ---------------------------------------------------------------------------

def mode_handshake():
    print(f"Connecting to {HOST}:{PORT} as {CALLSIGN} ...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10)
    sock.connect((HOST, PORT))
    print("--- PRE-LOGIN ---")
    print(read_for(sock, 3))
    sock.sendall((CALLSIGN + "\r\n").encode())
    time.sleep(LOGIN_WAIT)
    print("--- POST-LOGIN ---")
    print(read_for(sock, 2))
    sock.close()


# ---------------------------------------------------------------------------
# Mode 2: interactive
# ---------------------------------------------------------------------------

def mode_interactive():
    print(f"Connecting to {HOST}:{PORT} as {CALLSIGN} ...")
    sock = connect_and_login()
    print("Logged in.  Waiting for CCC > prompt...\n")

    stop = threading.Event()

    def _reader():
        fh = sock.makefile("r", errors="replace")
        for line in fh:
            if stop.is_set():
                break
            stripped = line.rstrip()
            if stripped:
                sys.stdout.write(f"\n[SERVER] {stripped}\n> ")
                sys.stdout.flush()

    t = threading.Thread(target=_reader, daemon=True)
    t.start()

    time.sleep(1.5)   # let the login banner clear
    print("Ready. Type CC Cluster commands. 'quit' or Ctrl-C to exit.")
    print("After each command, type: SH/FILTER  to see if it registered.\n")

    try:
        while True:
            try:
                cmd = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if cmd.lower() in ("quit", "exit", "q"):
                break
            if cmd:
                sock.sendall((cmd + "\r\n").encode())
    finally:
        stop.set()
        try:
            sock.close()
        except OSError:
            pass
        print("\nDisconnected.")


# ---------------------------------------------------------------------------
# Mode 3: probe
# ---------------------------------------------------------------------------

def mode_probe():
    print(f"Connecting to {HOST}:{PORT} as {CALLSIGN} ...")
    sock = connect_and_login()
    print(f"Logged in. Testing {len(PROBE_CMDS)} candidate commands.\n")
    print("=" * 70)

    for label, cmd in PROBE_CMDS:
        print(f"\n>>> [{label}]")
        print(f"    Sending: {cmd}")
        sock.sendall((cmd + "\r\n").encode())
        time.sleep(PAUSE)
        response = read_for(sock, PAUSE)
        # Filter to non-spot lines only (no "DX de ..." lines)
        lines = [l for l in response.splitlines()
                 if l.strip() and not l.startswith("DX de")]
        for line in lines:
            print(f"    {line}")

        # After every non-SH/FILTER command, auto-send SH/FILTER
        if "SH/FILTER" not in cmd:
            print(f"    [auto] SH/FILTER")
            sock.sendall(b"SH/FILTER\r\n")
            time.sleep(PAUSE)
            sh = read_for(sock, PAUSE)
            sh_lines = [l for l in sh.splitlines()
                        if l.strip() and not l.startswith("DX de")]
            for line in sh_lines:
                print(f"    {line}")

    print("\n" + "=" * 70)
    print("Probe complete.")
    sock.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="CC Cluster diagnostic tool")
    parser.add_argument("--interactive", action="store_true",
                        help="Interactive command shell")
    parser.add_argument("--probe", action="store_true",
                        help="Automatically probe candidate filter commands")
    args = parser.parse_args()

    if args.interactive:
        mode_interactive()
    elif args.probe:
        mode_probe()
    else:
        mode_handshake()


if __name__ == "__main__":
    main()
