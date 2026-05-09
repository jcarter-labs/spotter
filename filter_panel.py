"""Filter settings panel — Approach 1: structured checklist.

Layout: left pane = Spotter/DX location checkboxes + Apply/Reset buttons.
        right pane = raw SH/FILTER server response + Refresh/Reset buttons.

ACCEPT/SPOTS location commands (by_continent, by_prefix, call_continent,
call_prefix) are sent to CC Cluster but require live verification — the server
may silently ignore unknown syntax. SH/FILTER response in the right pane
confirms what actually took effect.
"""

import tkinter as tk
from tkinter import ttk

CONTINENTS   = ["NA", "SA", "EU", "AF", "AS", "OC"]
NA_DISTRICTS = ["W1", "W2", "W3", "W4", "W5", "W6",
                "W7", "W8", "W9", "W0", "VE", "XE"]
DX_PREFIXES  = ["JA", "BY", "VK", "ZL", "UA", "RA",
                "DL", "G",  "F",  "I",  "PY", "LU", "ZS", "VU", "HL"]

# Commands sent by Reset to clear everything and re-enable all spot types.
_RESET_CMDS = ["CLEAR/SPOTS ALL", "SET/FT8", "SET/FT4", "SET/CW"]


def _checkbox_grid(parent, labels, ncols=6):
    """Build a grid of checkboxes; return {label: BooleanVar}."""
    vars_ = {}
    for i, label in enumerate(labels):
        v = tk.BooleanVar()
        ttk.Checkbutton(parent, text=label, variable=v).grid(
            row=i // ncols, column=i % ncols, padx=3, sticky="w")
        vars_[label] = v
    return vars_


class FilterPanel(tk.Toplevel):
    def __init__(self, parent, conn, on_status_change):
        super().__init__(parent)
        self.title("Cluster Filter Settings")
        self.resizable(True, True)
        self.protocol("WM_DELETE_WINDOW", self.withdraw)  # hide, don't destroy

        self._conn = conn
        self._on_status_change = on_status_change  # callback(summary: str)

        self._sp_cont = {}
        self._sp_dist = {}
        self._dx_cont = {}
        self._dx_pfx  = {}

        self._build()

    # ── public ──────────────────────────────────────────────────────────────

    def append_server_line(self, line: str):
        """Append one raw cluster text line to the server status pane."""
        self._srv_txt.configure(state="normal")
        self._srv_txt.insert(tk.END, line + "\n")
        self._srv_txt.see(tk.END)
        self._srv_txt.configure(state="disabled")

    def clear_server_status(self):
        self._srv_txt.configure(state="normal")
        self._srv_txt.delete("1.0", tk.END)
        self._srv_txt.configure(state="disabled")

    # ── private: build ───────────────────────────────────────────────────────

    def _build(self):
        pane = tk.PanedWindow(self, orient=tk.HORIZONTAL,
                              sashrelief=tk.RAISED, sashwidth=5)
        pane.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        pane.add(self._build_left(pane),  minsize=370)
        pane.add(self._build_right(pane), minsize=260)

    def _build_left(self, parent):
        f = tk.Frame(parent, padx=10, pady=8)

        # Spotter section
        tk.Label(f, text="SPOTTER LOCATION",
                 font=("", 10, "bold")).pack(anchor="w")

        tk.Label(f, text="Continent", fg="gray").pack(anchor="w", pady=(5, 1))
        fg = tk.Frame(f); fg.pack(anchor="w")
        self._sp_cont = _checkbox_grid(fg, CONTINENTS, ncols=6)

        tk.Label(f, text="NA / US District", fg="gray").pack(anchor="w", pady=(7, 1))
        fg = tk.Frame(f); fg.pack(anchor="w")
        self._sp_dist = _checkbox_grid(fg, NA_DISTRICTS, ncols=6)

        ttk.Separator(f, orient="horizontal").pack(fill="x", pady=10)

        # DX section
        tk.Label(f, text="DX LOCATION",
                 font=("", 10, "bold")).pack(anchor="w")

        tk.Label(f, text="Continent", fg="gray").pack(anchor="w", pady=(5, 1))
        fg = tk.Frame(f); fg.pack(anchor="w")
        self._dx_cont = _checkbox_grid(fg, CONTINENTS, ncols=6)

        tk.Label(f, text="Major Prefixes", fg="gray").pack(anchor="w", pady=(7, 1))
        fg = tk.Frame(f); fg.pack(anchor="w")
        self._dx_pfx = _checkbox_grid(fg, DX_PREFIXES, ncols=5)

        # Buttons
        bf = tk.Frame(f)
        bf.pack(anchor="w", pady=(14, 4))
        ttk.Button(bf, text="Apply",
                   command=self._apply).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(bf, text="Reset all filters",
                   command=self._reset).pack(side=tk.LEFT)

        return f

    def _build_right(self, parent):
        f = tk.Frame(parent, padx=10, pady=8)

        tk.Label(f, text="SERVER STATUS",
                 font=("", 10, "bold")).pack(anchor="w")

        txt_frame = tk.Frame(f)
        txt_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

        self._srv_txt = tk.Text(txt_frame, width=34, height=22,
                                font=("Courier", 9), state="disabled",
                                wrap="none", bg="#f5f5f5")
        sb = ttk.Scrollbar(txt_frame, command=self._srv_txt.yview)
        self._srv_txt.configure(yscrollcommand=sb.set)
        self._srv_txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        bf = tk.Frame(f)
        bf.pack(anchor="w", pady=(8, 0))
        ttk.Button(bf, text="Refresh",
                   command=self._refresh).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(bf, text="Reset all filters",
                   command=self._reset).pack(side=tk.LEFT)

        return f

    # ── private: actions ─────────────────────────────────────────────────────

    def _apply(self):
        sp_conts = [c for c, v in self._sp_cont.items() if v.get()]
        sp_dists = [p for p, v in self._sp_dist.items() if v.get()]
        dx_conts = [c for c, v in self._dx_cont.items() if v.get()]
        dx_pfxs  = [p for p, v in self._dx_pfx.items()  if v.get()]

        self._conn.send_command("CLEAR/SPOTS ALL")

        sp_terms = ([f"by_continent {c}" for c in sp_conts] +
                    [f"by_prefix {p}"    for p in sp_dists])
        dx_terms = ([f"call_continent {c}" for c in dx_conts] +
                    [f"call_prefix {p}"    for p in dx_pfxs])

        slot = 1
        if sp_terms and dx_terms:
            # AND spotter+DX conditions within each slot
            for sp in sp_terms:
                for dx in dx_terms:
                    self._conn.send_command(f"ACCEPT/SPOTS {slot} {sp} {dx}")
                    slot += 1
        elif sp_terms:
            for sp in sp_terms:
                self._conn.send_command(f"ACCEPT/SPOTS {slot} {sp}")
                slot += 1
        elif dx_terms:
            for dx in dx_terms:
                self._conn.send_command(f"ACCEPT/SPOTS {slot} {dx}")
                slot += 1

        self._notify_status(sp_conts, sp_dists, dx_conts, dx_pfxs)
        self._refresh()

    def _reset(self):
        for cmd in _RESET_CMDS:
            self._conn.send_command(cmd)
        for v in (list(self._sp_cont.values()) + list(self._sp_dist.values()) +
                  list(self._dx_cont.values()) + list(self._dx_pfx.values())):
            v.set(False)
        self._on_status_change("⚠ TEST MODE — all spots")
        self._refresh()

    def _refresh(self):
        self.clear_server_status()
        self._conn.send_command("SH/FILTER")

    def _notify_status(self, sp_conts, sp_dists, dx_conts, dx_pfxs):
        sp = sp_conts + sp_dists
        dx = dx_conts + dx_pfxs
        parts = []
        if sp:
            parts.append(f"Spotters: {','.join(sp)}")
        if dx:
            parts.append(f"DX: {','.join(dx)}")
        summary = " | ".join(parts) if parts else "none"
        self._on_status_change(f"Filters: {summary}")
