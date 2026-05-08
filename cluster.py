import queue
import re
import socket
import threading
import time
from dataclasses import dataclass

BAND_RANGES = [
    ("160m", 1800, 2000),
    ("80m",  3500, 4000),
    ("60m",  5330, 5406),
    ("40m",  7000, 7300),
    ("30m", 10100, 10150),
    ("20m", 14000, 14350),
    ("17m", 18068, 18168),
    ("15m", 21000, 21450),
    ("12m", 24890, 24990),
    ("10m", 28000, 29700),
    ("6m",  50000, 54000),
]

_SPOT_RE = re.compile(
    r"DX de (\S+?):\s+([\d.]+)\s+(\S+)\s+(.*?)\s+(\d{4}Z)\s*$"
)


@dataclass
class Spot:
    dx_call: str
    spotter: str
    freq_khz: float
    band: str
    mode: str
    comment: str
    time_utc: str
    dx_dxcc: str = ""
    dx_continent: str = ""
    spotter_dxcc: str = ""
    spotter_continent: str = ""


def detect_band(freq_khz: float):
    for name, low, high in BAND_RANGES:
        if low <= freq_khz <= high:
            return name
    return None


def detect_mode(comment: str) -> str:
    c = comment.upper()
    if "FT8" in c:
        return "FT8"
    if "FT4" in c:
        return "FT4"
    if "RTTY" in c:
        return "RTTY"
    if "CW" in c:
        return "CW"
    if "SSB" in c or "USB" in c or "LSB" in c:
        return "SSB"
    return "UNKNOWN"


def parse_spot(line: str):
    m = _SPOT_RE.match(line.strip())
    if not m:
        return None
    spotter, freq_str, dx_call, comment, time_utc = m.groups()
    freq_khz = float(freq_str)
    band = detect_band(freq_khz) or "UNKNOWN"
    mode = detect_mode(comment)
    return Spot(
        dx_call=dx_call,
        spotter=spotter,
        freq_khz=freq_khz,
        band=band,
        mode=mode,
        comment=comment.strip(),
        time_utc=time_utc,
    )


class ClusterConnection:
    def __init__(self, host: str, port: int, callsign: str, spot_queue: queue.Queue):
        self._host = host
        self._port = port
        self._callsign = callsign
        self._queue = spot_queue
        self._stop_event = threading.Event()
        self._thread = None

    def start(self):
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1.0)

    def _read_loop(self):
        backoff = 5
        while not self._stop_event.is_set():
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(30.0)
                sock.connect((self._host, self._port))
                sock.settimeout(None)
                backoff = 5
                fh = sock.makefile("r", errors="replace")
                for line in fh:
                    if self._stop_event.is_set():
                        break
                    spot = parse_spot(line)
                    if spot:
                        try:
                            self._queue.put_nowait(spot)
                        except queue.Full:
                            pass
                sock.close()
            except Exception:
                if not self._stop_event.is_set():
                    self._stop_event.wait(backoff)
                    backoff = min(backoff * 2, 60)
