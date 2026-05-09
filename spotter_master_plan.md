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
| Mode filtering | CW only, always — hardcoded at server via SET/NOFT8, SET/NOFT4 |
| Location filtering | Server-side via CC Cluster commands (syntax TBD — verify before building UI) |
| Band filtering | Server-side once CC Cluster syntax confirmed; client-side for scope window |
| Skimmer spots | Show all, no distinction |
| Deduplication | Suppress same callsign+band within N minutes (configurable, default 10) |
| Band scope | Scrolling display, center freq ± configurable kHz, 10-min window |
| Click action | Send CAT to KX3 + copy callsign to clipboard (KX3 integration deferred) |
| Settings persistence | All display + filter settings saved to ~/.config/spotter/config.json |
| Definition of done | Connects, spots display, filters work, band scope shows activity, no crashes |

---

## Stack

- Python 3.13, macOS, Homebrew venv (`.venv/bin/python`)
- `socket` + `threading` (telnet, stdlib)
- `tkinter` + `ttk` (main window, filter panel, controls)
- `matplotlib` via `FigureCanvasTkAgg` (band scope)
- `re` (spot parsing)
- `json` (config persistence)
- `pyserial` (KX3 CAT — deferred)

Run command: `cd /Users/jc/code/spotter && .venv/bin/python main.py`
Test command: `cd /Users/jc/code/spotter && .venv/bin/python -m unittest discover -v tests/`
Config file:  `~/.config/spotter/config.json`

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
  live_test.py       # 60s live integration test, CLI flags for filters
  tests/
    test_cluster.py
    test_filters.py
    test_config.py
    test_ui.py
```

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
cd /Users/jc/code/spotter && .venv/bin/python cluster_debug.py --probe
cd /Users/jc/code/spotter && .venv/bin/python cluster_debug.py --interactive
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

### STAGE 3 — UI — IN PROGRESS

#### 3A — Band Scope ✅ COMPLETE

- `bandscope.py`: center freq ± configurable kHz, 10-min scrolling window,
  elapsed-time X axis (T=0 left, T=-10 right), frequency Y axis
- `main.py`: center freq entry, BW dropdown (10/20/50/100 kHz), dedup combobox,
  Filters… button, two-line status block (filter summary + connection)
- `scope_utils.py`: format_freq, extract_prefix, drain_queue
- Run: `cd /Users/jc/code/spotter && .venv/bin/python main.py`

#### 3B — Filter Panel ⚠ PARTIALLY COMPLETE

- `filter_panel.py`: Spotter/DX location checkboxes, server status pane,
  Apply/Reset/Refresh buttons — UI complete
- **Blocker**: Location filter commands (`ACCEPT/SPOTS by_continent` etc.) are
  silently rejected by CC Cluster. Correct syntax unknown.
- Mode checkboxes missing from panel (CW hardcoded in main.py — intentional)
- **Do not extend location filter UI until CC Cluster syntax is verified**

#### 3C — Pending: CC Cluster Syntax Verification

Goal: Find correct commands for spotter/DX location and band filtering.

Steps:
1. Extend `cluster_debug.py` with `--interactive` flag (readline loop, send
   commands, print responses) — **single runnable command to test syntax**
2. Connect via `cd /Users/jc/code/spotter && .venv/bin/python cluster_debug.py --interactive`
3. Probe candidate commands, observe SH/FILTER after each
4. Update the Verified table above
5. Only then add band/location checkboxes to filter panel

#### 3D — Pending: Band Selection in Filter Panel

- Checkboxes for HF bands: 80, 40, 30, 20, 17, 15, 10
- Server-side: send verified band filter commands on Apply
- "Ask" button: sends SH/FILTER, populates right-pane with raw response
- Scope window stays independent (center freq ± BW, not band-locked)

#### 3E — Pending: Cosmetic fixes (batch together, one commit)

- Remove center-frequency tick from left Y axis
- Fix callsign vertical centering on dash marker (slight downward offset needed)
- No other changes in this commit

#### 3F — Deferred: KX3 Integration

- Optional: detect `/dev/cu.usbserial-*`, instantiate RigController from kx3_logger
- Click spot → send CAT frequency, copy callsign to clipboard
- No CAT error shown if KX3 not connected

---

## Out of Scope

- Multiple simultaneous cluster connections
- ADIF export, contest scoring, log upload
- SQLite or any database
- Spot audio alerts
- DX entity awards tracking (DXCC, WAS, etc.)

---

## Collaboration Rules for Claude Code

### Commands must always be runnable

Every terminal command Claude provides must be a single line, copy-paste
ready, and verified to work on macOS. No comment lines mixed with executable
commands. No tools that require installation without stating so.

Example of what NOT to do:
```
# Filtered (20m only):           ← zsh will try to execute this
cd /Users/jc/code/spotter && .venv/bin/python live_test.py --band 20m
```

Example of correct form:
```bash
cd /Users/jc/code/spotter && .venv/bin/python live_test.py --band 20m
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
cd /Users/jc/code/spotter && .venv/bin/python cluster_debug.py --interactive
```
Type the command, observe the response, check SH/FILTER. If SH/FILTER does
not reflect the change, the command did not work.

### Platform check

Before recommending any CLI tool, confirm it exists on macOS without
installation. Prefer tools in the standard macOS install: `nc`, `python3`,
`curl`, `git`. Flag anything that requires `brew install`.
