import copy
import json
import os

DEFAULTS = {
    "host": "ve7cc.net",
    "port": 23,
    "callsign": "",
    "dedup_minutes": 10,
    "last_band": "20m",
    "filter": {
        "bands": [],
        "modes": [],
        "dx_prefixes": [],
        "dx_continents": [],
        "dx_dxcc": [],
        "spotter_prefixes": [],
        "spotter_continents": [],
        "spotter_dxcc": [],
    },
}


class Config:
    def __init__(self, path: str):
        self._path = path
        self.data = {}

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
