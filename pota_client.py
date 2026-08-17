import queue
import threading

import requests

from cluster import Spot, detect_band

POTA_URL = "https://api.pota.app/spot/activator"
POLL_SECONDS = 60
REQUEST_TIMEOUT_S = 10


def fetch_spots():
    """GET the current POTA activator spot list, normalized to CW-only Spots.

    Raises requests.RequestException on network/HTTP failure -- caller
    decides how to back off.
    """
    response = requests.get(POTA_URL, timeout=REQUEST_TIMEOUT_S)
    response.raise_for_status()
    raw_spots = response.json()

    spots = []
    for raw in raw_spots:
        spot = normalize_spot(raw)
        if spot is not None:
            spots.append(spot)
    return spots


def normalize_spot(raw: dict):
    """POTA JSON -> Spot, or None if unparseable or not CW.

    Tolerant of missing/extra fields -- POTA's schema is not a contract.
    Note: POTA's own `source` field (spot origin, e.g. "GT2"/"RBN") is
    unrelated to our internal `feed` tag and is intentionally not carried
    through.
    """
    try:
        mode = str(raw["mode"]).upper()
        if mode != "CW":
            return None
        freq_khz = float(raw["frequency"])
        dx_call = str(raw["activator"])
    except (KeyError, TypeError, ValueError):
        return None

    band = detect_band(freq_khz) or "UNKNOWN"

    return Spot(
        dx_call=dx_call,
        spotter=str(raw.get("spotter", "")),
        freq_khz=freq_khz,
        band=band,
        mode=mode,
        comment=str(raw.get("comments", "")),
        time_utc=str(raw.get("spotTime", "")),
        feed="POTA",
    )


def filter_to_window(spots, center_khz, bandwidth_khz):
    half = bandwidth_khz / 2.0
    lo, hi = center_khz - half, center_khz + half
    return [s for s in spots if lo <= s.freq_khz <= hi]


class PotaConnection:
    """Polls the POTA API on a daemon thread and pushes windowed, CW-only
    spots into its own queue -- kept separate from the DX-cluster spot_queue
    so POTA spots never pass through DedupCache (see master plan Stage 4C).
    """

    def __init__(self, spot_queue: queue.Queue, window_fn,
                 poll_seconds: int = POLL_SECONDS):
        self._queue = spot_queue
        self._window_fn = window_fn  # () -> (center_khz, bandwidth_khz)
        self._poll_seconds = poll_seconds
        self._stop_event = threading.Event()
        self._thread = None

    def start(self):
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1.0)

    def _poll_loop(self):
        backoff = 5
        while not self._stop_event.is_set():
            try:
                spots = fetch_spots()
            except requests.RequestException:
                if not self._stop_event.is_set():
                    self._stop_event.wait(backoff)
                    backoff = min(backoff * 2, 60)
                continue

            backoff = 5
            center_khz, bandwidth_khz = self._window_fn()
            for spot in filter_to_window(spots, center_khz, bandwidth_khz):
                try:
                    self._queue.put_nowait(spot)
                except queue.Full:
                    pass

            self._stop_event.wait(self._poll_seconds)
