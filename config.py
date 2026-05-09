import copy
import json
import os

DEFAULT_PATH = os.path.expanduser("~/.config/spotter/config.json")

DEFAULTS = {
    "host": "ve7cc.net",
    "port": 23,
    "callsign": "N6YU",
    "dedup_minutes": 10,
    "center_khz": 14025.0,
    "bandwidth_khz": 50.0,
    "last_band": "20m",
    "filter": {
        "modes": ["CW"],
        "bands": [],
        "dx_continents": [],
        "spotter_continents": [],
    },
}


class Config:
    def __init__(self, path: str = DEFAULT_PATH):
        self._path = path
        self.data = {}

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value

    def load(self):
        self.data = copy.deepcopy(DEFAULTS)
        if os.path.exists(self._path):
            try:
                with open(self._path) as f:
                    saved = json.load(f)
                self._merge(self.data, saved)
            except (json.JSONDecodeError, OSError):
                pass

    def save(self):
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, "w") as f:
            json.dump(self.data, f, indent=2)

    def _merge(self, base: dict, override: dict):
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge(base[key], value)
            else:
                base[key] = value
