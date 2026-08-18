# DX Spotter

CW-only DX cluster spot monitor. Connects to a DX cluster via telnet and to
the POTA activator API, and plots both on a band scope. Windows, macOS,
Linux.

## Features

- Band scope: fixed-column frequency strip, spots fade with age, no time axis
- Two independent lanes: DX-cluster/RBN spots (left, ticked) and POTA
  activator spots (right, plain text) — same color, never overwrite each other
- Server-side CW filtering (`SET/NOFT8`, `SET/NOFT4`)
- Server-side band, country, and US-state filters via CC Cluster `SET/FILTER`
- POTA spots are CW-only, filtered to the scope's current center/BW, polled
  every 60s, no dedup (POTA's feed is a live snapshot, not an event stream)
- Filter panel: location/band controls, raw `SH/FILTER` readout, live spot log
- Click a spot to copy its callsign to the clipboard
- Settings persist in `~/.config/spotter/config.json`

## Install

```
git clone git@github.com:jcarter-labs/spotter.git
cd spotter
python -m venv .venv
pip install matplotlib requests
```

Activate the venv before running anything:

| Platform | Command |
|---|---|
| macOS/Linux | `source .venv/bin/activate` |
| Windows (PowerShell) | `.venv\Scripts\Activate.ps1` |
| Windows (cmd) | `.venv\Scripts\activate.bat` |

macOS: if `tkinter` is missing, `brew install python-tk@3.13`.

## Run

```
python main.py
```

Toolbar (right of scope): center kHz, bandwidth (10/20/50/100 kHz), window
(1/5/10/30 min — scope history and fade rate), Filters button. Footer shows
filter summary, POTA/cluster connection status, and an aging-color legend.

## Files

| File | Purpose |
|---|---|
| `main.py` | Entry point — window, controls, poll loop |
| `cluster.py` | Telnet connection, spot parser, `Spot` dataclass |
| `pota_client.py` | POTA API polling worker (`PotaConnection`) |
| `bandscope.py` | Band scope widget (`tk.Frame`) |
| `filter_panel.py` | Filter settings window (`tk.Toplevel`) |
| `filters.py` | `DedupCache`, DXCC prefix lookup |
| `config.py` | JSON config load/save |
| `scope_utils.py` | Pure helpers: `format_freq`, `extract_prefix`, `drain_queue` |
| `cluster_debug.py` | CC Cluster diagnostic tool |
| `live_test.py` | Live cluster spot stream to stdout |
| `live_pota_test.py` | Live POTA spot stream / schema probe |
| `tests/` | Unit tests (65, no live network) |

```
python cluster_debug.py                # login handshake
python cluster_debug.py --interactive  # type commands, see raw responses
python cluster_debug.py --probe        # automated filter syntax probe
python live_test.py --band 20m         # 60s cluster stream, one band
python live_pota_test.py --probe       # dump raw POTA JSON + field types
python live_pota_test.py --duration 30 # poll live POTA API, print spots
```

## Config

`~/.config/spotter/config.json`, created on first run. Defaults:

```
host: ve7cc.net, port: 23, callsign: N6YU
center_khz: 14025.0, bandwidth_khz: 50.0, window_minutes: 10
dedup_minutes: 10, last_band: 20m
filter: {modes: [CW], bands: [], dx_continents: [], spotter_continents: []}
```

## Verified CC Cluster filter commands (ve7cc.net)

```
SET/FILTER DXBM/REJECT 160,80,40,30,17,15,12,10,6   # 20m only
SET/FILTER DOC/PASS K,VE                            # spotter country
SET/FILTER DOS/PASS CA,OR,WA                        # spotter US state
SET/FILTER DXCTY/PASS JA                            # DX country
SET/FILTER DXSTATE/PASS CA                          # DX US state
UNSET/FILTER                                        # clear all
```

Country prefixes use CTY.DAT notation: USA = `K` (not `W`), Canada = `VE`.
US call districts (W1–W0) aren't filterable — state is the finest granularity.

## Tests

```
python -m unittest discover -v tests/
```
