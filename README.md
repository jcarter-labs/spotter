# DX Spotter

A DX cluster spot monitor for macOS. Connects to a single DX cluster via
Telnet, displays incoming spots in a filterable list, and plots activity
on a graphical band scope. Clicking a spot tunes the KX3 via CAT and
copies the callsign to the clipboard.

---

## Requirements

- macOS
- Python 3
- pyserial (`pip install pyserial`)
- matplotlib (`pip install matplotlib`)
- Elecraft KX3 connected via USB (optional — for CAT tuning)

---

## Setup

```bash
git clone git@github.com:jcarter-labs/spotter.git
cd spotter
python3 -m venv .venv
source .venv/bin/activate
pip install pyserial matplotlib
```

---

## Run

```bash
source .venv/bin/activate
python main.py
```

Cluster address and port are read from `~/.config/spotter/config.json`.
Default cluster is set at first launch. KX3 is auto-detected on
`/dev/cu.usbserial-*` — if not present, clipboard copy still works.

---

## Calling Diagram

```
main.py
├── Config()                   [config.py]
│     └── ~/.config/spotter/config.json  [filesystem]
│
├── queue.Queue()              [stdlib]
│
├── ClusterConnection(host, port, callsign, queue)  [cluster.py]
│     └── start()
│           └── _read_loop()       [daemon thread]
│                 ├── socket.socket()    [stdlib / DX cluster server]
│                 ├── _reconnect()       [exponential backoff]
│                 └── parse_spot()
│                       ├── detect_band()
│                       ├── detect_mode()
│                       └── prefix_to_dxcc()  [filters.py]
│                             └── queue.put()
│
├── SpotFilter()               [filters.py]
│     └── passes(spot)
│           └── DedupCache.is_dup()
│
└── MainWindow()               [ui.py]
      ├── _poll_spots()            [via tkinter after() loop]
      │     ├── queue.get_nowait()
      │     ├── SpotFilter.passes()
      │     ├── Treeview.insert()
      │     └── BandScope.update()     [bandscope.py]
      │           └── FigureCanvasTkAgg  [matplotlib - external]
      │
      ├── _on_spot_click()
      │     ├── RigController (CAT → KX3)  [kx3_logger/rig.py - optional]
      │     └── clipboard copy
      │
      ├── _on_filter_change()
      │     └── SpotFilter rebuild
      │
      └── mainloop()               [tkinter - external]

On window close:
  ├── ClusterConnection.stop()
  └── Config.save()
```

---

## Filtering

Spots can be filtered by any combination of:
- **Band** — 160m through 6m
- **Mode** — CW, SSB, FT8, FT4, RTTY
- **DX prefix** — e.g. UA, JA, VK
- **DX continent** — NA, SA, EU, AF, AS, OC
- **DX DXCC entity** — e.g. Russia, Japan
- **Spotter prefix / continent**

Deduplication suppresses repeated spots for the same callsign+band
within a configurable time window (default 10 minutes).

---

## Project Status

- [x] Stage 1 — Cluster connection and spot parser (`cluster.py`) — not started
- [ ] Stage 2 — Filter engine and config (`filters.py`, `config.py`) — not started
- [ ] Stage 3 — UI, band scope, KX3 integration — not started

---

## Out of Scope

Multiple cluster connections, ADIF export, contest scoring, dupe checking
beyond time window, DX awards tracking, spot audio alerts.
