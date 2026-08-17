# DX Spotter — Prototype Master Plan
# Development Plan for Claude Code

## Project Overview

DX cluster spot monitor for desktop (Windows, macOS, Linux). Connects to a single DX cluster via
Telnet, displays incoming spots in a filterable list, and plots activity
on a per-band graphical band scope. Clicking a spot sends the frequency
to the KX3 via CAT and copies the callsign to the clipboard.

---

## Decisions

| Question | Decision |
|---|---|
| Platform | Desktop, cross-platform (Windows, macOS, Linux) |
| Cluster connection | Hardcoded default, editable in config file |
| Simultaneous clusters | One |
| Mode filtering | CW only, always — hardcoded at server via SET/NOFT8, SET/NOFT4 |
| Location filtering | Server-side via CC Cluster commands (syntax TBD — verify before building UI) |
| Band filtering | Server-side once CC Cluster syntax confirmed; client-side for scope window |
| Skimmer spots | Show all, no distinction |
| Deduplication | Suppress same callsign+band within N minutes (configurable, default 10) |
| Band scope | Static fixed-column frequency strip (no time axis), center freq ± configurable kHz, window 1/5/10/30 min (default 10) — see Architecture → Band Scope Behavior |
| Click action | Send CAT to KX3 + copy callsign to clipboard (KX3 integration deferred) |
| Settings persistence | All display + filter settings saved to ~/.config/spotter/config.json |
| POTA spots | Public API, CW-only, filtered to live scope window, own right-edge lane (no tick/leader, no dedup, no color distinction) — see Stage 4 |
| Definition of done | Connects, spots display, filters work, band scope shows activity, no crashes |

---

## Stack

- Python 3.13, cross-platform venv (macOS/Linux: `.venv/bin/python`; Windows: `.venv\Scripts\python.exe`)
- `socket` + `threading` (telnet, stdlib)
- `tkinter` + `ttk` (main window, filter panel, controls)
- `matplotlib` via `FigureCanvasTkAgg` (band scope)
- `re` (spot parsing)
- `json` (config persistence)
- `pyserial` (KX3 CAT — deferred)
- `requests` (POTA API polling — Stage 4, **not yet installed**: `pip install requests`, and add a `requirements.txt`)

Activate venv: macOS/Linux `source .venv/bin/activate` · Windows (PowerShell) `.venv\Scripts\Activate.ps1` · Windows (cmd) `.venv\Scripts\activate.bat`
Run command: `python main.py` (from project root, venv activated)
Test command: `python -m unittest discover -v tests/` (venv activated)
Config file:  `~/.config/spotter/config.json` (resolved via `os.path.expanduser`, works on Windows too — expands under the user's home directory on all three platforms)

---

## Architecture

### Module Layout (current)

```
spotter/
  main.py            # Entry point, main window, control bar, poll loop
  cluster.py         # Telnet connection, spot parser, send_command(), text_queue
  filters.py         # DedupCache, prefix_to_dxcc
  config.py          # JSON settings load/save
  bandscope.py       # matplotlib band scope widget
  filter_panel.py    # Cluster filter settings window (Toplevel)
  scope_utils.py     # Pure helpers: format_freq, extract_prefix, drain_queue
  cluster_debug.py   # Raw handshake diagnostic tool
  live_test.py       # 60s live integration test, CLI flags for filters + --host/--port
  pota_client.py     # Stage 4 (not built): POTA API polling worker, mirrors ClusterConnection
  live_pota_test.py  # Stage 4 (not built): live POTA smoke test + --probe schema-verification mode
  tests/
    test_cluster.py
    test_filters.py
    test_config.py
    test_ui.py
    test_pota.py     # Stage 4 (not built): mocked-HTTP unit tests, no live network
```

### Band Scope Behavior (current)

- **Layout**: fixed-width scope column (left) + vertical toolbar (right) —
  center-freq entry, BW dropdown (10/20/50/100 kHz), window dropdown
  (1/5/10/30 min), Filters… button. Footer holds a two-line status block
  (filter summary + connection) and a color-coded aging legend (2/5/10 min
  swatches).
- **Display model**: static fixed-column frequency strip, not a scrolling
  time axis — every visible spot renders at the same x position, so
  closeness in frequency is closeness on screen. Ticks (`ax.hlines`) sit at
  the exact `spot.freq_khz`; callsign labels are vertically decluttered via
  isotonic regression under a min-row-spacing constraint (pool-adjacent-
  violators), with a leader line back to the tick whenever a label is
  displaced past a small pixel threshold. Tick-to-label gap is measured
  from real font metrics, not a fixed-points offset, so it holds up under
  any dpi/zoom.
- **Aging**: spots fade via alpha (full opacity when fresh, toward a floor
  near the window cutoff) rather than moving position. A periodic
  `self.after()` repaint (every 5s) keeps fade/expiry current even with no
  new incoming spots. `fade_alpha()` (`bandscope.py`) is shared by the
  footer legend so the legend swatches match the scope's actual curve.
- **Spot identity**: keyed by `(dx_call, band)` — one live entry per
  station. A re-spot refreshes that station's age/frequency in place
  instead of stacking a duplicate row. (Separate from `filters.py`'s
  `DedupCache`, which suppresses duplicate spot-list entries within N
  minutes — dedup is enforced but no longer user-adjustable from the
  toolbar.)
- **Interaction**: clicking the scope copies the nearest callsign (by
  frequency distance) to the system clipboard — precedes full KX3 CAT
  integration (Stage 3G, deferred).
- **Planned extension**: a second, independent spot source (POTA) is
  specced in Stage 4 but not yet built — it will render in its own
  right-edge lane rather than change anything described above. This
  subsection stays accurate as the sole description of DX-cluster/RBN
  rendering; update it (don't just append) once Stage 4 actually ships.

### Concurrency Model

- Main thread: tkinter event loop
- Worker thread: daemon thread in cluster.py reads telnet lines
- Spot IPC: `queue.Queue` — worker puts parsed Spot objects, UI polls via `after(200)`
- Text IPC: `text_queue` — non-spot cluster lines (SH/FILTER responses etc.) routed to filter panel
- `send_command()` is thread-safe via `_sock_lock`; callable from UI thread

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

## CC Cluster Commands — Verified

All commands tested live against ve7cc.net CC Cluster 3.397.

### Mode (always on at connect)

| Command | Effect |
|---|---|
| `SET/SKIMMER` | Enable skimmer/RBN spots |
| `SET/NOFT8` | Disable FT8 spots |
| `SET/NOFT4` | Disable FT4 spots |
| `SET/FT8` / `SET/FT4` | Re-enable for test mode |

### Band filter — DXBM (DX Band Mode)

Strategy: specify bands to REJECT; everything else passes.
Band codes: `160`, `80`, `40`, `30`, `20`, `17`, `15`, `12`, `10`, `6`

| Goal | Command |
|---|---|
| 20m only | `SET/FILTER DXBM/REJECT 160,80,40,30,17,15,12,10,6` |
| 20m + 40m | `SET/FILTER DXBM/REJECT 160,80,30,17,15,12,10,6` |
| All HF (no band filter) | `UNSET/FILTER` |

SH/FILTER confirms: `BandMode Filter set to Reject: 160-CW,80-CW,...`

### Spotter country filter — DOC (DX Spot Origin Country)

Uses CTY.DAT country prefixes — NOT callsign prefixes.
Key mapping: USA = `K` (not `W`); Canada = `VE`; Mexico = `XE`.

| Goal | Command |
|---|---|
| US spotters only | `SET/FILTER DOC/PASS K` |
| US + Canada spotters | `SET/FILTER DOC/PASS K,VE` |
| NA spotters | `SET/FILTER DOC/PASS K,VE,XE` |
| EU spotters | `SET/FILTER DOC/PASS G,F,I,DL,EA,OH,SM,LA,OZ,PA,ON,HB,OE,OK,OM,HA,YO,LZ,SV,YU,9A,S5` |

SH/FILTER confirms: `DX Spot Orig Cty Filter/All set to Pass: K,VE`

### DX country filter — DXCTY

Uses same CTY.DAT prefixes.

| Goal | Command |
|---|---|
| DX in Japan only | `SET/FILTER DXCTY/PASS JA` |
| DX in EU | `SET/FILTER DXCTY/PASS G,F,I,DL,EA,...` |
| No DX filter | `UNSET/FILTER` |

SH/FILTER confirms: `DX CTY Filter/All set to Pass: JA`

### Reset

`UNSET/FILTER` — clears all user filters. The cluster keeps its own
default reject for VHF (2m, 70cm, MW) regardless.

### State filter — DXSTATE (DX station state) and DOS (spotter state)

Both verified — multi-state comma lists work. Two equivalent syntaxes:

| Goal | Command |
|---|---|
| DX in California | `SET/FILTER DXSTATE/PASS CA` or `SET/FILTER DXSTATE CA` |
| DX in CA, OR, WA | `SET/FILTER DXSTATE/PASS CA,OR,WA` |
| Spotters in California | `SET/FILTER DOS/PASS CA` or `SET/FILTER DOS CA` |
| Spotters in CA, OR, WA | `SET/FILTER DOS/PASS CA,OR,WA` |

SH/FILTER confirms: `DX State Filter/All set to Pass: CA,OR,WA`

### What does NOT work (confirmed via probe)

| Command tried | Result |
|---|---|
| `ACCEPT/SPOTS N by_continent NA` | Silently ignored |
| `SET/ORIGIN NA`, `SET/SPOTTER NA` | "command error" |
| `SET/SPOTORIGCTY NA`, `SET/DXCTY EU` | "command error" |
| `SET/BAND 20`, `SET/NOBAND 40` | "command error" |
| `CLEAR/SPOTS ALL` | Silently ignored |
| `W` as country prefix for USA | "Invalid standard country prefix" |
| `SET/DXSTATE CA`, `SET/DOS CA` | "command error" (needs `SET/FILTER` prefix) |
| `SET/FILTER DX_STATE/PASS CA` | "Invalid filter name" |
| `SET/FILTER DOCSTATE/PASS CA` | "Invalid filter name" |

### US call district vs state — important distinction

**Call district filtering (W1, W2, W6…):** not a native CC Cluster capability.
Call districts are not geographic entities in CTY.DAT and are only heuristically
derivable from callsigns. The cluster does not expose a district filter.

**State filtering (CA, TX, OR…):** fully supported server-side via `DXSTATE` and
`DOS`. The cluster already computes and stores state metadata internally, as
confirmed by the `SH/FILTER` fields `DX State` and `DX Spot Orig State`.

Filter panel implication: replace the W1–W0 district checkboxes with a US state
selector using two-letter postal codes (CA, TX, OR, WA, etc.).

### Diagnostic commands

```bash
python cluster_debug.py --probe
python cluster_debug.py --interactive
```

---

## TDD Stages

---

### STAGE 1 — Cluster Connection and Parser ✅ COMPLETE

47 unit tests passing. Live test verified.

---

### STAGE 2 — Filter Engine and Config ✅ COMPLETE

Server-side mode filtering (CW only) verified live. Client-side dedup working.

---

### STAGE 3 — UI — IN PROGRESS (3A–3F complete, 3G remains)

#### 3A — Band Scope ✅ COMPLETE (superseded by 3F — see Architecture → Band Scope Behavior for current design)

Original delivery: `bandscope.py` (center freq ± configurable kHz), `main.py`
controls, `scope_utils.py` (format_freq, extract_prefix, drain_queue). The
initial design used a scrolling elapsed-time X axis and a top toolbar with a
dedup combobox — both replaced in 3F. Run: `python main.py` (venv activated).

#### 3B — Filter Panel ✅ COMPLETE

- `filter_panel.py`: three-pane layout — location/band checkboxes (left),
  server status (middle), SPOTS LOG (right, green bg) showing each passing
  spot as `TIME  FREQ  DX_CALL  de SPOTTER`
- Apply/Reset/Refresh buttons send verified `SET/FILTER` commands; Reset
  re-applies CW-only mode (`SET/NOFT8`/`SET/NOFT4`) instead of clearing it
- `SET/NOSSB` removed from `cluster.py` — not a valid CC Cluster command
- Mode checkboxes intentionally absent (CW hardcoded, enforced server-side)

#### 3C — CC Cluster Syntax Verification ✅ COMPLETE

Verified live against ve7cc.net CC Cluster 3.397 via `cluster_debug.py
--interactive`. Working commands: `DXBM` (band reject list), `DOC`/`DXCTY`
(spotter/DX country via CTY.DAT prefixes), `DXSTATE`/`DOS` (spotter/DX US
state, two-letter postal codes). See "CC Cluster Commands — Verified" above
for the full table, including confirmed non-working commands and the
call-district vs state distinction (districts are not server-filterable).

#### 3D — Band Selection in Filter Panel ✅ COMPLETE

- `PANEL_BANDS` checkboxes (80/40/30/20/17/15/10) in `filter_panel.py`,
  all-checked = no band filter; unchecking sends `SET/FILTER DXBM/REJECT`
  with the excluded bands
- "Refresh" button sends `SH/FILTER`, response routed to server-status pane
  via `text_queue`
- Scope window stays independent of band selection (center freq ± BW)

#### 3E — Cosmetic fixes ✅ COMPLETE

- Center-frequency tick removed from left Y axis
- Marker switched from `marker="_"` + annotate to `ax.hlines()` at the exact
  `spot.freq_khz` data coordinate; callsign label uses `va="center"` at the
  same y so it sits centered on the tick, starting just right of its edge
- Window size now a `window_minutes` param (1/5/10/30 min dropdown in
  `main.py`, persisted in config) rather than a hardcoded constant
- Click on scope copies nearest callsign to system clipboard (QRZ lookup
  prep) — precedes full KX3 CAT integration below
- Tick-to-label gap fixed (measured font metrics, dpi/zoom-independent) and
  overlapping labels decluttered (isotonic regression / PAV, bounded
  leader-line length) — see Architecture → Band Scope Behavior for the
  current mechanism.

#### 3F — Static Frequency Strip, Side Toolbar, Aging Legend ✅ COMPLETE

Reworked 3A's scrolling time-axis band scope into the static fixed-column
display, and 3A's top toolbar into the side-toolbar layout — done because
the time axis let a frequency-near, time-distant spot push a label away
from its tick even with nothing actually overlapping on screen. Full current
behavior documented in Architecture → Band Scope Behavior (this entry is a
changelog, not the spec). Also dropped the dedup-minutes combobox as
redundant with the new fade-based aging display.

#### 3G — Deferred: KX3 Integration

- Optional: detect serial port (macOS `/dev/cu.usbserial-*`, Linux `/dev/ttyUSB*`, Windows `COM*`), instantiate RigController from kx3_logger
- Click spot → send CAT frequency (clipboard-copy half already done in 3E)
- No CAT error shown if KX3 not connected

---

### STAGE 4 — POTA Spot Integration — NOT STARTED

Adds a second spot source (POTA activator spots) to the band scope, shown in
a visually separate lane from DX-cluster/RBN spots so no new color is
needed. This is the full spec for the feature; nothing below is built yet.

#### 4A — POTA API Client

- Public endpoint, no authentication required: `GET https://api.pota.app/spot/activator`
- Poll interval: 60s, hardcoded — no config toggle for v1
- `pota_client.py`: a `PotaConnection`-style class mirrors `ClusterConnection`
  (`cluster.py`) — daemon thread, `start()`/`stop()`, backoff on failure
  (5s doubling to a 60s cap), same shape as the existing telnet worker
- Pushes normalized spots into its **own queue**, not the shared
  `spot_queue` — drained separately in `main.py._poll()`. This is what
  keeps POTA spots out of `DedupCache` entirely (see 4C)
- New dependency: `requests` — **not yet installed** in `.venv` (see Stack)
- HTTP errors, including `429 Too Many Requests`, trigger the same backoff
  as a connection failure; no immediate retry
- `main.py._on_close()` must stop this worker alongside `self._conn.stop()`
- **Schema verified live** via `live_pota_test.py --probe` (2026-08-16, 71
  spots returned). Confirmed: `activator`, `frequency` (string, inconsistent
  decimals e.g. `"7076"` / `"14058.0"`), `mode`, `reference`, `locationDesc`,
  `spotTime` (no timezone suffix — do not parse for aging, see 4B),
  `expire` (int seconds, highly variable — ignored, see 4B). `parkName` is
  usually `null`; the real park name is in `name` instead (moot for v1,
  neither is displayed).
- **Important: POTA's JSON has its own `source` field**, unrelated to our
  internal feed tag — values seen include `"GT2"` (POTA's own app/web
  spotter) and `"RBN"` (POTA's own RBN-auto-spot integration). Confirms
  POTA's feed already blends in RBN-detected activations, separate from
  our app's DX-cluster/RBN skimmer feed — i.e. the same call+band showing
  up in both of our lanes is a real, expected case, not a rare edge case
  (see 4D). To avoid colliding with POTA's own `source` field, our
  internal per-spot tag is named `feed`, not `source` (see 4B) — this
  field is simply not carried through from the JSON.

#### 4B — Normalization and Filtering

- `Spot` (`cluster.py`) gains a `feed` field (default e.g. `"DXCLUSTER"`,
  `"POTA"` for this source) — used only to route rendering into the correct
  lane (4D), not for color. Named `feed` rather than `source` specifically
  to avoid colliding with POTA's own unrelated `source` JSON field (see 4A)
- POTA JSON → `Spot`: `activator` → `dx_call`, `frequency` (string kHz) →
  `freq_khz` (float), `band` via `cluster.detect_band()` (reused, not
  reimplemented), `mode` uppercased and filtered to `CW` only — non-CW
  entries dropped before reaching the queue
- Frequency filter: current live `center_khz ± bandwidth_khz/2`, read
  directly off `BandScope`'s existing instance attributes at filter time —
  no added locking; a plain attribute read is treated as sufficient here
  (KISS, not a strict correctness requirement)
- POTA's own `expire` field is ignored — aging follows the same
  `fade_alpha()` / `window_minutes` model as every other spot (4D)
- POTA's `spotTime` is not used for aging — age is measured from local
  receipt time, exactly like cluster spots, avoiding clock-skew/timezone
  parsing bugs

#### 4C — No Deduplication for POTA

- `filters.DedupCache` is not applied to the POTA queue. POTA's endpoint
  returns a live snapshot of currently-active spots on every poll (state,
  not a discrete event stream like the telnet feed), so "suppress a
  repeat" doesn't apply the way it does to cluster spots
- A still-active station is simply refreshed in place by the POTA lane's
  own spot store (4D) — the same "one live entry per station" principle
  as the cluster lane, just without a dedup-suppression pass upstream

#### 4D — Rendering: Independent Right-Edge Lane

- POTA spots render in a second, independent lane on the right edge of the
  scope, separate from the existing tick-hugging cluster/RBN lane —
  chosen instead of a color distinction (avoids a second color and a
  legend entry)
- Same navy color and the same `fade_alpha()` aging curve as cluster spots
  — lane position is the only visual differentiator
- No tick mark and no leader line for POTA spots — plain right-justified
  text (`ha="right"`), placed directly at the post-declutter y position;
  frequency is conveyed by y-coordinate alone, not an exact tick
- POTA labels get their own decluttering pass — the existing
  `_declutter_y()` (isotonic regression / pool-adjacent-violators) is
  reused unchanged, called a second time on the POTA-only subset. The two
  lanes never need to coordinate with each other since they're spatially
  disjoint
- Storage is independent per lane (effectively keyed by
  `(call, band, feed)`, not the shared `(call, band)` key
  `BandScope._spots` currently uses) — a station spotted via both POTA and
  cluster/RBN in the same window renders in **both** lanes simultaneously;
  neither evicts the other
- `bandscope.py`'s figure widened ~40% (from `figsize=(1.9, 6)`) so both
  lanes have room without labels meeting in the middle — an assumption
  ("callsigns rarely fill more than half the window") to verify visually
  once built, not proven up front

#### 4E — Status and Testing

- Footer gains a POTA connection status indicator, styled like the
  existing DX-cluster status line (`self._conn_status_var` pattern)
- `live_pota_test.py`: live smoke test against the real API (mirrors
  `live_test.py`), plus a `--probe` mode (mirrors `cluster_debug.py
  --probe`) — run once during development to confirm the real JSON shape
  before the normalizer in 4B is written
- `tests/test_pota.py`: mocked HTTP (`unittest.mock.patch("requests.get")`),
  no live network — covers CW/band-window filtering, missing/extra JSON
  fields tolerated without crashing, `feed` tagging, and independent
  two-lane storage (same call+band from both sources renders as two
  entries, not one)

---

## Out of Scope

- Multiple simultaneous cluster connections
- ADIF export, contest scoring, log upload
- SQLite or any database
- Spot audio alerts
- DX entity awards tracking (DXCC, WAS, etc.)
- POTA/RBN spot correlation or merging (matching a POTA activation to an
  RBN reception report) — Stage 4 renders them as independent, uncorrelated
  lanes; purely visual side-by-side, no cross-source matching logic

---

## Collaboration Rules for Claude Code

### Commands must always be runnable

Every terminal command Claude provides must be a single line, copy-paste
ready, and verified to work in the user's actual shell on their actual
platform (bash/zsh on macOS/Linux, PowerShell or cmd on Windows). No comment
lines mixed with executable commands — `#` breaks a command line in
bash/zsh/PowerShell alike. No tools that require installation without
stating so.

Example of what NOT to do:
```
# Filtered (20m only):           ← shell will try to execute this
python live_test.py --band 20m
```

Example of correct form:
```bash
python live_test.py --band 20m
```

If a command requires a tool that may not be installed (e.g. telnet, gh),
state the install command first on its own line.

### Verify external behavior before building UI

Do not write UI for a server-side feature until the server command is
confirmed to work. Build the diagnostic tool first, confirm the behavior,
then build the UI. This prevents shipping filter panels that silently do
nothing (which already happened once with location filters).

Order: **Verify → Build → Test → Commit**

### Session scope vs commit scope

Sessions can cover multiple related features — that is efficient and fine.
Commits should be focused on one concern per commit:
- Cosmetic fixes in one commit
- Functional changes in another
- Infrastructure changes (adding a queue, changing an API) in another

This makes it easy to isolate regressions. It does not mean one feature per
session — it means don't mix unrelated concerns in a single commit.

### State what is unverified

If a feature depends on unverified external behavior, say so in the commit
message and in comments in the code. Do not present aspirational features as
working. The location filter checkboxes should have been labeled "pending
syntax verification" in the commit message.

### Runnable test for every new server interaction

Any new CC Cluster command must have a one-line test that can be run before
the feature is merged:
```bash
python cluster_debug.py --interactive
```
Type the command, observe the response, check SH/FILTER. If SH/FILTER does
not reflect the change, the command did not work.

### Platform check

Before recommending any CLI tool, confirm it exists on the user's platform
without additional installation. Prefer tools available by default across
macOS, Linux, and Windows: `python`, `git`. Flag anything that requires a
package-manager install (Homebrew on macOS, apt on Linux, winget/choco on
Windows) — `nc`/`curl` in particular are not guaranteed present on Windows.
