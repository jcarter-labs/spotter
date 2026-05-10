"""Cluster filter settings panel.

All commands verified live against ve7cc.net CC Cluster 3.397.

Spotter location:
  SET/FILTER DOC/PASS K,VE          — country (CTY.DAT prefix, USA=K not W)
  SET/FILTER DOS/PASS CA,OR,WA      — US state (two-letter postal code)

DX location:
  SET/FILTER DXCTY/PASS JA          — country (CTY.DAT prefix)
  SET/FILTER DXSTATE/PASS CA        — US state

Band (reject all except selected):
  SET/FILTER DXBM/REJECT 80,40,...  — reject listed bands; rest pass through

Reset:
  UNSET/FILTER                       — clear all user location/band filters
  SET/NOFT8 + SET/NOFT4             — ensure CW-only (always sent)

Note: call districts (W1/W6...) are not filterable at CC Cluster.
      State filtering (CA/OR/WA...) is the finest US granularity available.
"""

import tkinter as tk
from tkinter import ttk

# Bands shown in panel. All checked = no band filter sent.
PANEL_BANDS = ["80", "40", "30", "20", "17", "15", "10"]

# Continent → curated CTY.DAT prefix lists (major entities only)
_CTY = {
    "NA": "K,VE,XE",
    "EU": "G,F,I,DL,SP,EA,OH,SM,LA,OZ,PA,ON,HB9,OE,OK,OM,HA,YO,LZ,SV,YU,9A,S5,UR,LY,YL,ES",
    "AS": "JA,BY,HL,VU,JT,UA9,UA0,9M2,BV",
    "SA": "PY,LU,CE,OA,CP,CX,HK,YV,HC,ZP",
    "AF": "ZS,5H,9J,ZE,CN,6W,TZ,ST2",
    "OC": "VK,ZL,T8,KH6",
}

# W6/W7 state presets (useful for local-spotter band scope)
_W6 = "CA,NV,AZ"
_W7 = "OR,WA,ID,MT,WY,UT"


class FilterPanel(tk.Toplevel):
    def __init__(self, parent, conn, on_status_change):
        super().__init__(parent)
        self.title("Cluster Filter Settings")
        self.resizable(True, True)
        self.protocol("WM_DELETE_WINDOW", self.withdraw)

        self._conn = conn
        self._on_status_change = on_status_change  # callback(summary: str)

        self._sp_cty   = tk.StringVar()
        self._sp_state = tk.StringVar()
        self._dx_cty   = tk.StringVar()
        self._dx_state = tk.StringVar()
        self._band_vars = {b: tk.BooleanVar(value=True) for b in PANEL_BANDS}

        self._build()

    # ── public API ───────────────────────────────────────────────────────────

    def append_server_line(self, line: str):
        self._srv_txt.configure(state="normal")
        self._srv_txt.insert(tk.END, line + "\n")
        self._srv_txt.see(tk.END)
        self._srv_txt.configure(state="disabled")

    def clear_server_status(self):
        self._srv_txt.configure(state="normal")
        self._srv_txt.delete("1.0", tk.END)
        self._srv_txt.configure(state="disabled")

    def append_spot_line(self, spot):
        line = (f"{spot.time_utc}  {spot.freq_khz:8.1f}  "
                f"{spot.dx_call:<10}  de {spot.spotter}")
        self._spot_txt.configure(state="normal")
        self._spot_txt.insert(tk.END, line + "\n")
        self._spot_txt.see(tk.END)
        self._spot_txt.configure(state="disabled")

    def clear_spots_log(self):
        self._spot_txt.configure(state="normal")
        self._spot_txt.delete("1.0", tk.END)
        self._spot_txt.configure(state="disabled")

    # ── build ────────────────────────────────────────────────────────────────

    def _build(self):
        outer = tk.PanedWindow(self, orient=tk.HORIZONTAL,
                               sashrelief=tk.RAISED, sashwidth=5)
        outer.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        outer.add(self._build_left(outer),  minsize=360)
        outer.add(self._build_right(outer), minsize=270)

    def _build_left(self, parent):
        f = tk.Frame(parent, padx=10, pady=8)

        tk.Label(f, text="Mode: CW  (applied at connect, always)",
                 fg="gray", font=("", 9, "italic")).pack(anchor="w", pady=(0, 8))

        tk.Label(f, text="SPOTTER LOCATION",
                 font=("", 10, "bold")).pack(anchor="w")
        self._entry_row(f, "Country (CTY.DAT):", self._sp_cty,
                        presets=[("NA", _CTY["NA"]), ("EU", _CTY["EU"]),
                                 ("AS", _CTY["AS"])])
        self._entry_row(f, "US State:", self._sp_state,
                        presets=[("W6", _W6), ("W7", _W7),
                                 ("W6+7", f"{_W6},{_W7}")])

        ttk.Separator(f, orient="horizontal").pack(fill="x", pady=10)

        tk.Label(f, text="DX LOCATION",
                 font=("", 10, "bold")).pack(anchor="w")
        self._entry_row(f, "Country (CTY.DAT):", self._dx_cty,
                        presets=[("NA",  _CTY["NA"]),  ("EU",  _CTY["EU"]),
                                 ("AS",  _CTY["AS"]),  ("OC",  _CTY["OC"])])
        self._entry_row(f, "US State:", self._dx_state, presets=[])

        ttk.Separator(f, orient="horizontal").pack(fill="x", pady=10)

        tk.Label(f, text="BAND  (uncheck = exclude at server)",
                 font=("", 10, "bold")).pack(anchor="w")
        bf = tk.Frame(f); bf.pack(anchor="w", pady=(5, 0))
        for i, band in enumerate(PANEL_BANDS):
            ttk.Checkbutton(bf, text=f"{band}m",
                            variable=self._band_vars[band]).grid(
                                row=0, column=i, padx=4)
        sb = tk.Frame(f); sb.pack(anchor="w", pady=(3, 0))
        ttk.Button(sb, text="All",  command=self._bands_all).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(sb, text="None", command=self._bands_none).pack(side=tk.LEFT)

        ttk.Separator(f, orient="horizontal").pack(fill="x", pady=10)

        btnf = tk.Frame(f); btnf.pack(anchor="w")
        ttk.Button(btnf, text="Apply",
                   command=self._apply).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btnf, text="Reset all filters",
                   command=self._reset).pack(side=tk.LEFT)
        return f

    def _build_right(self, parent):
        vpane = tk.PanedWindow(parent, orient=tk.VERTICAL,
                               sashrelief=tk.RAISED, sashwidth=4)
        vpane.add(self._build_server_status(vpane), minsize=150)
        vpane.add(self._build_spots_log(vpane),     minsize=150)
        return vpane

    def _build_server_status(self, parent):
        f = tk.Frame(parent, padx=8, pady=6)
        tk.Label(f, text="SERVER STATUS",
                 font=("", 10, "bold")).pack(anchor="w")
        tf = tk.Frame(f); tf.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        self._srv_txt = tk.Text(tf, width=36, height=12,
                                font=("Courier", 9), state="disabled",
                                wrap="none", bg="#f5f5f5")
        sb = ttk.Scrollbar(tf, command=self._srv_txt.yview)
        self._srv_txt.configure(yscrollcommand=sb.set)
        self._srv_txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        bf = tk.Frame(f); bf.pack(anchor="w", pady=(6, 0))
        ttk.Button(bf, text="Refresh",
                   command=self._refresh).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(bf, text="Reset all filters",
                   command=self._reset).pack(side=tk.LEFT)
        return f

    def _build_spots_log(self, parent):
        f = tk.Frame(parent, padx=8, pady=6)
        tk.Label(f, text="SPOTS LOG",
                 font=("", 10, "bold")).pack(anchor="w")
        tf = tk.Frame(f); tf.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        self._spot_txt = tk.Text(tf, width=36, height=12,
                                 font=("Courier", 9), state="disabled",
                                 wrap="none", bg="#f0f8f0")
        sb = ttk.Scrollbar(tf, command=self._spot_txt.yview)
        self._spot_txt.configure(yscrollcommand=sb.set)
        self._spot_txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        bf = tk.Frame(f); bf.pack(anchor="w", pady=(6, 0))
        ttk.Button(bf, text="Clear",
                   command=self.clear_spots_log).pack(side=tk.LEFT)
        return f

    # ── helpers ──────────────────────────────────────────────────────────────

    def _entry_row(self, parent, label, var, presets):
        tk.Label(parent, text=label, fg="gray").pack(anchor="w", pady=(5, 1))
        row = tk.Frame(parent); row.pack(anchor="w", fill="x")
        ttk.Entry(row, textvariable=var, width=26).pack(side=tk.LEFT)
        for lbl, val in presets:
            ttk.Button(row, text=lbl, width=len(lbl)+1,
                       command=lambda v=val, sv=var: sv.set(v)).pack(
                           side=tk.LEFT, padx=(3, 0))

    def _bands_all(self):
        for v in self._band_vars.values(): v.set(True)

    def _bands_none(self):
        for v in self._band_vars.values(): v.set(False)

    # ── actions ──────────────────────────────────────────────────────────────

    def _apply(self):
        self._conn.send_command("UNSET/FILTER")
        self._conn.send_command("SET/NOFT8")
        self._conn.send_command("SET/NOFT4")

        cmds, parts = [], []

        sp_cty = self._sp_cty.get().strip()
        if sp_cty:
            cmds.append(f"SET/FILTER DOC/PASS {sp_cty}")
            parts.append(f"Spotters:{sp_cty}")

        sp_state = self._sp_state.get().strip()
        if sp_state:
            cmds.append(f"SET/FILTER DOS/PASS {sp_state}")
            parts.append(f"Spotter state:{sp_state}")

        dx_cty = self._dx_cty.get().strip()
        if dx_cty:
            cmds.append(f"SET/FILTER DXCTY/PASS {dx_cty}")
            parts.append(f"DX:{dx_cty}")

        dx_state = self._dx_state.get().strip()
        if dx_state:
            cmds.append(f"SET/FILTER DXSTATE/PASS {dx_state}")
            parts.append(f"DX state:{dx_state}")

        checked = {b for b, v in self._band_vars.items() if v.get()}
        reject  = [b for b in PANEL_BANDS if b not in checked]
        if reject and checked:
            cmds.append(f"SET/FILTER DXBM/REJECT {','.join(reject)}")
            bands_str = ",".join(f"{b}m" for b in PANEL_BANDS if b in checked)
            parts.append(f"Bands:{bands_str}")

        for cmd in cmds:
            self._conn.send_command(cmd)

        summary = " | ".join(parts) if parts else "none"
        self._on_status_change(f"Filters: {summary}")
        self._refresh()

    def _reset(self):
        self._conn.send_command("UNSET/FILTER")
        self._conn.send_command("SET/NOFT8")
        self._conn.send_command("SET/NOFT4")
        self._sp_cty.set("")
        self._sp_state.set("")
        self._dx_cty.set("")
        self._dx_state.set("")
        self._bands_all()
        self._on_status_change("Filters: none")
        self._refresh()

    def _refresh(self):
        self.clear_server_status()
        self._conn.send_command("SH/FILTER")
