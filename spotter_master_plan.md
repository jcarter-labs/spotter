# DX Spotter — Prototype Master Plan
# Development Plan for Claude Code

## Project Overview

DX cluster spot monitor for macOS. Connects to a single DX cluster via
Telnet, displays incoming spots in a filterable list, and plots activity
on a per-band graphical band scope. Clicking a spot sends the frequency
to the KX3 via CAT and copies the callsign to the clipboard.

---

## Decisions

| Question | Decision |
|---|---|
| Platform | macOS only |
| Cluster connection | Hardcoded default, editable in config file |
| Simultaneous clusters | One |
| Filtering | Band + DXCC entity + Continent + Prefix + Mode |
| Skimmer spots | Show all, no distinction |
| Deduplication | Suppress same callsign+band within N minutes (configurable, default 10) |
| Band scope | One band at a time, user selects |
| Click action | Send CAT to KX3 + copy callsign to clipboard |
| Settings persistence | Cluster address + all filter settings saved to JSON |
| Definition of done | Connects, spots display, filters work, band scope shows activity, no crashes |

---

## Stack

- Python 3, macOS
- `socket` + `threading` (telnet, stdlib)
- `tkinter` + `ttk.Treeview` (spot list, filter panel)
- `matplotlib` via `FigureCanvasTkAgg` (band scope)
- `re` (spot parsing, filtering)
- `json` (config persistence)
- `pyserial` (KX3 CAT, reuse from kx3_logger)
- No database

Config file: `~/.config/spotter/config.json`

---

## Architecture

### Module Layout

```
spotter/
  main.py          # Entry point
  cluster.py       # Telnet connection, spot parser, reconnect
  filters.py       # Filter engine, DXCC prefix lookup, band/mode detection
  config.py        # JSON settings load/save
  bandscope.py     # matplotlib band scope widget
  ui.py            # tkinter main window, Treeview, filter panel
  tests/
    test_cluster.py
    test_filters.py
    test_config.py
```

### Concurrency Model

- Main thread: tkinter event loop
- Worker thread: daemon thread in cluster.py, reads telnet lines
- IPC: `queue.Queue` — worker puts parsed Spot objects, UI polls via `after()`
- No shared mutable state outside the Queue

### Spot Data Model

```python
@dataclass
class Spot:
    dx_call: str        # spotted callsign
    spotter: str        # spotter callsign
    freq_khz: float     # frequency in kHz
    band: str           # "20m", "40m", etc.
    mode: str           # "CW", "SSB", "FT8", "FT4", "RTTY", "UNKNOWN"
    comment: str        # raw comment field
    time_utc: str       # "1234Z"
    dx_dxcc: str        # DXCC entity name
    dx_continent: str   # continent code: NA, SA, EU, AF, AS, OC, AN
    spotter_dxcc: str
    spotter_continent: str
```

### Spot Line Format (DX cluster standard)

```
DX de W1AW:      14025.0  UA9MA        CW 599                         1234Z
```
Regex: `DX de (\S+):\s+([\d.]+)\s+(\S+)\s+(.*?)\s+(\d{4}Z)`

---

## Band Frequency Ranges (kHz)

| Band | Low | High |
|---|---|---|
| 160m | 1800 | 2000 |
| 80m | 3500 | 4000 |
| 60m | 5330 | 5406 |
| 40m | 7000 | 7300 |
| 30m | 10100 | 10150 |
| 20m | 14000 | 14350 |
| 17m | 18068 | 18168 |
| 15m | 21000 | 21450 |
| 12m | 24890 | 24990 |
| 10m | 28000 | 29700 |
| 6m | 50000 | 54000 |

---

## Mode Detection (from comment field)

- FT8: comment contains "FT8"
- FT4: comment contains "FT4"
- RTTY: comment contains "RTTY"
- CW: comment contains "CW" or "cw"
- SSB: comment contains "SSB", "USB", or "LSB"
- UNKNOWN: none of the above

---

## TDD Stages

---

### STAGE 1 — Cluster Connection and Parser (cluster.py)

Goal: Verified telnet connection, spot parsing, and queue population before any UI.

#### Unit Tests (test_cluster.py) — write tests first

1. test_parse_valid_spot
   - Input: `"DX de W1AW:      14025.0  UA9MA        CW 599                         1234Z"`
   - Assert: dx_call="UA9MA", spotter="W1AW", freq_khz=14025.0, time_utc="1234Z"

2. test_parse_malformed_line
   - Input: login banner, blank line, non-spot text
   - Assert: returns None (no exception)

3. test_band_detection
   - 14025.0 → "20m", 7100.0 → "40m", 99999.0 → None

4. test_mode_detection
   - Comment "CW 599" → "CW"
   - Comment "FT8 -10dB" → "FT8"
   - Comment "nice one" → "UNKNOWN"

5. test_queue_populated_on_valid_line
   - Mock socket to yield one valid spot line
   - Assert queue receives one Spot object within 500ms

6. test_malformed_lines_do_not_populate_queue
   - Mock socket to yield banner text only
   - Assert queue empty after 500ms

7. test_thread_stops_cleanly
   - Call stop() on ClusterConnection
   - Assert thread joins within 1s

#### Implementation Targets (cluster.py)

- `ClusterConnection(host, port, callsign, queue)`
  - `start()` — launches daemon thread
  - `stop()` — signals exit via threading.Event
  - `_read_loop()` — connects socket, reads lines, parses, queues Spot objects
  - `_reconnect()` — exponential backoff, max 60s, logs attempt count
- `parse_spot(line: str) → Spot | None`
- `detect_band(freq_khz: float) → str | None`
- `detect_mode(comment: str) → str`

#### Stage 1 Done Criteria

All 7 unit tests pass with mocked socket.
Manual test: connect to a live cluster, print spots to stdout for 30 seconds.

---

### STAGE 2 — Filter Engine and Config (filters.py, config.py)

Goal: Verified filtering logic and persistent settings before UI.

#### Unit Tests (test_filters.py) — write tests first

1. test_band_filter
   - SpotFilter(bands=["20m"]) accepts 20m spot, rejects 40m spot

2. test_mode_filter
   - SpotFilter(modes=["CW","FT8"]) accepts CW, rejects SSB

3. test_dx_prefix_filter
   - SpotFilter(dx_prefixes=["UA"]) accepts UA9MA, rejects W1AW

4. test_dx_continent_filter
   - SpotFilter(dx_continents=["EU"]) accepts EU spot, rejects NA spot

5. test_dx_dxcc_filter
   - SpotFilter(dx_dxcc=["Russia"]) accepts Russian spot, rejects US spot

6. test_spotter_prefix_filter
   - SpotFilter(spotter_prefixes=["W"]) accepts W1AW spotter, rejects VE7CC

7. test_combined_filters
   - Multiple active filters — all must pass (AND logic)

8. test_no_filters_passes_all
   - Empty SpotFilter passes any spot

9. test_dedup_suppresses_within_window
   - Same callsign+band twice within 10 min → second suppressed

10. test_dedup_passes_after_window
    - Same callsign+band after window expires → passes

#### Unit Tests (test_config.py) — write tests first

1. test_default_config_created_if_missing
   - Point Config at temp path; assert defaults loaded

2. test_save_and_reload
   - Save config with known values; reload; assert values match

3. test_partial_config_merges_defaults
   - Config file missing some keys; assert missing keys get defaults

#### Implementation Targets (filters.py)

- `SpotFilter` dataclass: bands, modes, dx_prefixes, dx_continents, dx_dxcc,
  spotter_prefixes, spotter_continents, spotter_dxcc (all lists, empty = no filter)
- `passes(spot: Spot, f: SpotFilter) → bool`
- `DedupCache(window_minutes: int)` — `is_dup(spot) → bool`, `record(spot)`
- `prefix_to_dxcc(callsign: str) → tuple[str, str]` — returns (dxcc_name, continent)
  Uses bundled prefix table dict (top ~40 DXCC entities by activity)

#### Implementation Targets (config.py)

- `Config(path: str)`
  - `load()` — reads JSON, merges missing keys with defaults
  - `save()` — writes JSON, creates parent dirs if needed
  - `defaults` dict: host, port, callsign, dedup_minutes, last_band, filter settings

#### Stage 2 Done Criteria

All 13 unit tests pass.

---

### STAGE 3 — UI (ui.py, bandscope.py, main.py)

Goal: Working application — spots display, filters apply, band scope renders, KX3 integration active.

#### Tests — logic only

1. test_format_freq — 14025.0 → "14025.0 kHz"
2. test_callsign_prefix — extract_prefix("UA9MA") → "UA"
3. test_queue_drain_returns_latest — multiple spots queued, drain returns most recent

#### Implementation Targets (ui.py)

- `MainWindow(tk.Tk)`
  - Left panel: `ttk.Treeview` spot list — columns: time, dx_call, freq, band, mode, spotter, comment
  - Right panel: filter controls (band checkboxes, mode checkboxes, prefix entry fields, continent dropdowns)
  - Bottom: status bar (connection state, spot count, last spot time)
  - Band selector dropdown (feeds band scope)
  - `_poll_spots()` — `after(200)` loop; drains queue; applies filter; inserts to Treeview; updates band scope
  - `_on_spot_click()` — sends CAT to KX3, copies dx_call to clipboard
  - `_on_filter_change()` — rebuilds SpotFilter, re-renders visible spots

#### Implementation Targets (bandscope.py)

- `BandScope(tk.Frame)`
  - Embeds `matplotlib FigureCanvasTkAgg`
  - X axis: frequency range for selected band
  - Y axis: time (newest at top, 30 min window)
  - Spots plotted as markers, labeled with dx_call
  - `update(spots: list[Spot], band: str)` — redraws plot
  - Click on marker triggers same action as Treeview click

#### Implementation Targets (main.py)

- Load Config
- Instantiate Queue, ClusterConnection, DedupCache, SpotFilter, MainWindow
- Wire ClusterConnection.start() before mainloop()
- On window close: ClusterConnection.stop(), save Config, exit

#### KX3 Integration

- Optional: if `/dev/cu.usbserial-*` present, instantiate RigController from kx3_logger
- Clicking a spot: send `FA` + zero-padded frequency via CAT, copy dx_call to clipboard
- If KX3 not connected: clipboard copy only, no CAT error shown

#### Stage 3 Done Criteria

- Application launches and connects to cluster without error
- Spots appear in Treeview within 5 seconds of connect
- All filter controls affect displayed spots immediately
- Band scope updates as spots arrive
- Clicking a spot copies callsign to clipboard
- Clicking a spot tunes KX3 if connected
- Settings persist between launches
- No crashes on cluster disconnect/reconnect

---

## Out of Scope

- Multiple simultaneous cluster connections
- ADIF export
- Dupe checking beyond simple time window
- Contest scoring
- Log upload
- SQLite or any database
- Skimmer/human spot distinction
- Spot audio alerts
- DX entity awards tracking (DXCC, WAS, etc.)

---

## Notes for Claude Code

- Write tests before implementation in Stage 1 and Stage 2.
- Stage 3 UI is iterative — no test gate required.
- Use unittest (stdlib); do not introduce pytest.
- Mock socket using unittest.mock.patch for all network tests.
- Keep all modules under 200 lines; refactor if exceeded.
- No global mutable state.
- All timestamps UTC only.
- pyserial and matplotlib are the only permitted third-party dependencies.
- Reuse rig.py from kx3_logger for KX3 CAT — do not duplicate.
