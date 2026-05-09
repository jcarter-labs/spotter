"""Pure utility functions shared by bandscope.py and tests — no GUI dependencies."""
import queue


def format_freq(freq_khz: float) -> str:
    return f"{freq_khz:.1f} kHz"


def extract_prefix(callsign: str) -> str:
    """Return the letter prefix before the first digit (e.g. 'UA9MA' -> 'UA')."""
    prefix = ""
    for ch in callsign.upper():
        if ch.isalpha():
            prefix += ch
        elif ch.isdigit():
            break
    return prefix


def drain_queue(q: queue.Queue) -> list:
    spots = []
    while True:
        try:
            spots.append(q.get_nowait())
        except queue.Empty:
            break
    return spots
