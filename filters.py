import time
from dataclasses import dataclass, field

# Sorted longest-first so UA9 matches before UA
_PREFIX_TABLE = [
    ("UA9", "Russia", "AS"), ("UA0", "Russia", "AS"),
    ("AA", "United States", "NA"), ("AB", "United States", "NA"),
    ("AC", "United States", "NA"), ("AD", "United States", "NA"),
    ("AE", "United States", "NA"), ("AF", "United States", "NA"),
    ("AG", "United States", "NA"), ("AI", "United States", "NA"),
    ("AJ", "United States", "NA"), ("AK", "United States", "NA"),
    ("DS", "South Korea", "AS"), ("HL", "South Korea", "AS"),
    ("BY", "China", "AS"), ("BV", "Taiwan", "AS"),
    ("4X", "Israel", "AS"), ("4Z", "Israel", "AS"),
    ("JA", "Japan", "AS"), ("JH", "Japan", "AS"),
    ("JI", "Japan", "AS"), ("JK", "Japan", "AS"),
    ("JR", "Japan", "AS"),
    ("VK", "Australia", "OC"), ("ZL", "New Zealand", "OC"),
    ("ZS", "South Africa", "AF"),
    ("PY", "Brazil", "SA"), ("LU", "Argentina", "SA"),
    ("CE", "Chile", "SA"),
    ("VE", "Canada", "NA"), ("VA", "Canada", "NA"),
    ("XE", "Mexico", "NA"),
    ("UA", "Russia", "EU"), ("RA", "Russia", "EU"),
    ("RK", "Russia", "EU"), ("RM", "Russia", "EU"),
    ("RN", "Russia", "EU"), ("RU", "Russia", "EU"),
    ("RV", "Russia", "EU"), ("RW", "Russia", "EU"),
    ("RX", "Russia", "EU"), ("RY", "Russia", "EU"),
    ("RZ", "Russia", "EU"),
    ("DL", "Germany", "EU"), ("DF", "Germany", "EU"),
    ("DG", "Germany", "EU"), ("DJ", "Germany", "EU"),
    ("DK", "Germany", "EU"), ("DM", "Germany", "EU"),
    ("SP", "Poland", "EU"), ("EA", "Spain", "EU"),
    ("OH", "Finland", "EU"), ("SM", "Sweden", "EU"),
    ("LA", "Norway", "EU"), ("OZ", "Denmark", "EU"),
    ("PA", "Netherlands", "EU"), ("ON", "Belgium", "EU"),
    ("HB", "Switzerland", "EU"), ("OE", "Austria", "EU"),
    ("OK", "Czech Republic", "EU"), ("OM", "Slovakia", "EU"),
    ("HA", "Hungary", "EU"), ("YO", "Romania", "EU"),
    ("LZ", "Bulgaria", "EU"), ("SV", "Greece", "EU"),
    ("YU", "Serbia", "EU"), ("9A", "Croatia", "EU"),
    ("S5", "Slovenia", "EU"),
    ("VU", "India", "AS"), ("JT", "Mongolia", "AS"),
    ("G", "England", "EU"), ("M", "England", "EU"),
    ("F", "France", "EU"), ("I", "Italy", "EU"),
    ("K", "United States", "NA"), ("N", "United States", "NA"),
    ("W", "United States", "NA"),
]

# Pre-sorted by prefix length descending for correct longest-match
_PREFIX_TABLE.sort(key=lambda x: len(x[0]), reverse=True)


def prefix_to_dxcc(callsign: str) -> tuple:
    call = callsign.upper()
    for prefix, dxcc, continent in _PREFIX_TABLE:
        if call.startswith(prefix):
            return dxcc, continent
    return "Unknown", ""


@dataclass
class SpotFilter:
    bands: list = field(default_factory=list)
    modes: list = field(default_factory=list)
    dx_prefixes: list = field(default_factory=list)
    dx_continents: list = field(default_factory=list)
    dx_dxcc: list = field(default_factory=list)
    spotter_prefixes: list = field(default_factory=list)
    spotter_continents: list = field(default_factory=list)
    spotter_dxcc: list = field(default_factory=list)


def passes(spot, f: SpotFilter) -> bool:
    if f.bands and spot.band not in f.bands:
        return False
    if f.modes and spot.mode not in f.modes:
        return False
    if f.dx_prefixes and not any(spot.dx_call.upper().startswith(p.upper()) for p in f.dx_prefixes):
        return False
    if f.dx_continents and spot.dx_continent not in f.dx_continents:
        return False
    if f.dx_dxcc and spot.dx_dxcc not in f.dx_dxcc:
        return False
    if f.spotter_prefixes and not any(spot.spotter.upper().startswith(p.upper()) for p in f.spotter_prefixes):
        return False
    if f.spotter_continents and spot.spotter_continent not in f.spotter_continents:
        return False
    if f.spotter_dxcc and spot.spotter_dxcc not in f.spotter_dxcc:
        return False
    return True


class DedupCache:
    def __init__(self, window_minutes: int = 10):
        self._window = window_minutes * 60
        self._seen = {}

    def is_dup(self, spot) -> bool:
        key = (spot.dx_call.upper(), spot.band)
        last = self._seen.get(key)
        if last is None:
            return False
        return (time.monotonic() - last) < self._window

    def record(self, spot):
        key = (spot.dx_call.upper(), spot.band)
        self._seen[key] = time.monotonic()
