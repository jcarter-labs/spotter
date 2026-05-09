# DX Spotter

CW-only DX cluster spot monitor for macOS. Connects to a DX cluster via
telnet, plots incoming spots on a scrolling band scope, and lets you filter
spots by band, spotter country, and DX country at the server.

## Features

- Scrolling band scope — center freq ± configurable kHz, 10-min window
- Server-side CW filtering (`SET/NOFT8`, `SET/NOFT4`) — no FT8 clutter
- Server-side band and country filters via CC Cluster `SET/FILTER` commands
- Adjustable bandwidth (10 / 20 / 50 / 100 kHz) and dedup window (1 / 10 / 30 min)
- Filter panel with `SH/FILTER` server status readout and Reset (test mode)
- Settings persist across sessions in `~/.config/spotter/config.json`

---

## Installation

```bash
git clone git@github.com:jcarter-labs/spotter.git
cd spotter
python3 -m venv .venv
source .venv/bin/activate
pip install matplotlib
brew install python-tk@3.13   # if tkinter is missing
```

> **Python version:** use `.venv/bin/python` (Homebrew Python 3.13 + Tk 9.0).
> The macOS system Python 3.9 links against Tk 8.5 which crashes on macOS 26.

---

## Usage

```bash
cd /Users/jc/code/spotter && .venv/bin/python main.py
```

Controls in the main window:

| Control | What it does |
|---|---|
| Center kHz + Set | Recenters the band scope |
| BW kHz | Bandwidth: 10 / 20 / 50 / 100 kHz full span |
| Dedup min | Suppress repeated callsign+band for N minutes |
| Filters… | Opens the cluster filter settings panel |

---

## Python Scripts

| File | Purpose | Run directly? |
|---|---|---|
| `main.py` | App entry point — main window, controls, poll loop | `cd /Users/jc/code/spotter && .venv/bin/python main.py` |
| `cluster.py` | Telnet connection, spot parser, `send_command()` | No — imported |
| `cluster_debug.py` | CC Cluster diagnostic tool (handshake / interactive / probe) | Yes — see below |
| `live_test.py` | 60-second live spot stream to stdout with optional filters | Yes — see below |
| `bandscope.py` | matplotlib band scope widget (`tk.Frame`) | No — imported |
| `filter_panel.py` | Cluster filter settings window (`tk.Toplevel`) | No — imported |
| `filters.py` | `DedupCache`, `prefix_to_dxcc` lookup table | No — imported |
| `config.py` | JSON config load/save | No — imported |
| `scope_utils.py` | Pure helpers: `format_freq`, `extract_prefix`, `drain_queue` | No — imported |
| `tests/test_cluster.py` | Unit tests: cluster, parser, filter commands | Via test runner |
| `tests/test_filters.py` | Unit tests: dedup, prefix lookup | Via test runner |
| `tests/test_config.py` | Unit tests: config load/save | Via test runner |
| `tests/test_ui.py` | Unit tests: scope_utils helpers | Via test runner |

### cluster_debug.py

```bash
.venv/bin/python cluster_debug.py                  # raw login handshake
.venv/bin/python cluster_debug.py --interactive    # interactive command shell
.venv/bin/python cluster_debug.py --probe          # automated filter syntax probe
```

### live_test.py

```bash
.venv/bin/python live_test.py                      # all CW spots, 60 seconds
.venv/bin/python live_test.py --band 20m           # 20m only
.venv/bin/python live_test.py --mode ""            # no mode filter (FT8 included)
.venv/bin/python live_test.py --duration 30        # shorter run
```

---

## Key Classes and Functions

### `cluster.py`

**`ClusterConnection(host, port, callsign, spot_queue, cluster_filter, text_queue)`**
Manages the telnet connection in a daemon thread. Parsed `Spot` objects go to
`spot_queue`; raw non-spot cluster text (e.g. `SH/FILTER` responses) goes to
`text_queue`.

- `start()` / `stop()` — start or cleanly stop the reader thread
- `send_command(cmd)` — thread-safe; sends a raw CC Cluster command from any thread

**`ClusterFilter`** — dataclass: `modes`, `bands`, `dx_continents`, `spotter_continents`.
Translated to `SET/NOFT8` / `SET/NOFT4` commands at connect time via `to_cc_commands()`.

**`parse_spot(line)`** — parses a raw `DX de …` line into a `Spot` dataclass or `None`.

### `bandscope.py`

**`BandScope(parent, center_khz, bandwidth_khz)`** — `tk.Frame` with an embedded
matplotlib figure. Displays spots as dash markers on a scrolling elapsed-time vs.
frequency plot (T=0 at left, T=−10min at right).

- `set_center(freq_khz)` — recenters the scope
- `set_bandwidth(bandwidth_khz)` — changes the frequency span
- `add_spots(spots)` — appends new spots and redraws

### `filter_panel.py`

**`FilterPanel(parent, conn, on_status_change)`** — `tk.Toplevel` with:
- Left pane: spotter / DX location checkboxes; Apply sends `SET/FILTER` commands
- Right pane: raw `SH/FILTER` server response; Refresh re-queries; Reset clears all

### `filters.py`

**`DedupCache(window_minutes)`** — suppresses repeated `(callsign, band)` pairs within the window.
**`prefix_to_dxcc(callsign)`** — returns `(dxcc_name, continent)` from a built-in prefix table.

### `config.py`

**`Config(path)`** — JSON config with `get(key)` / `set(key, value)` / `load()` / `save()`.
Defaults: `host`, `port`, `callsign`, `center_khz`, `bandwidth_khz`, `dedup_minutes`.

---

## Development Notes

### Run tests

```bash
cd /Users/jc/code/spotter && .venv/bin/python -m unittest discover -v tests/
```

47 tests, all passing.

### Config file

`~/.config/spotter/config.json` — created on first run with defaults. Delete to reset.

### Verified CC Cluster filter commands (ve7cc.net)

```
SET/FILTER DXBM/REJECT 160,80,40,30,17,15,12,10,6   # 20m only
SET/FILTER DOC/PASS K,VE                              # US + Canada spotters only
SET/FILTER DXCTY/PASS JA                              # DX in Japan only
UNSET/FILTER                                          # clear all location/band filters
```

Country prefixes use CTY.DAT notation: USA = `K` (not `W`), Canada = `VE`.
US call districts (W1–W0) cannot be filtered at the cluster — all map to `K`.

### Debugging

```bash
.venv/bin/python cluster_debug.py --interactive   # type commands, see raw responses
```

Type `SH/FILTER` in the interactive shell to see current server-side filter state.
