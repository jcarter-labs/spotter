import queue
import tkinter as tk
from tkinter import ttk

from bandscope import BandScope, fade_alpha
from cluster import ClusterConnection, ClusterFilter
from config import Config
from filter_panel import FilterPanel
from filters import DedupCache
from scope_utils import drain_queue

POLL_MS         = 200
BW_OPTIONS      = ["10", "20", "50", "100"]
WINDOW_OPTIONS  = ["1", "5", "10", "30"]
LEGEND_AGES_MIN = [2, 5, 10]
_NAVY           = (0, 0, 128)


def _blend_with_white(rgb, alpha):
    r, g, b = rgb
    r = int(r * alpha + 255 * (1 - alpha))
    g = int(g * alpha + 255 * (1 - alpha))
    b = int(b * alpha + 255 * (1 - alpha))
    return f"#{r:02x}{g:02x}{b:02x}"


class SpotterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("DX Spotter")
        self.geometry("460x760")
        self.resizable(True, True)

        self._config = Config()
        self._config.load()
        self._spot_queue = queue.Queue()
        self._text_queue = queue.Queue()
        self._dedup = DedupCache(window_minutes=self._config.get("dedup_minutes", 10))
        self._conn = None
        self._filter_panel = None

        self._build_ui()
        self._connect()
        self._poll()

    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self):
        # Footer (status + aging legend) is packed first so it reserves its
        # space at the bottom before the scope/toolbar row expands to fill
        # whatever's left.
        footer = tk.Frame(self, padx=8, pady=6)
        footer.pack(side=tk.BOTTOM, fill=tk.X)

        status_row = tk.Frame(footer)
        status_row.pack(side=tk.TOP, fill=tk.X)

        self._filter_status_var = tk.StringVar(value="Filters: none")
        tk.Label(status_row, textvariable=self._filter_status_var,
                 fg="#c07000", font=("", 9)).pack(side=tk.LEFT)

        self._conn_status_var = tk.StringVar(value="Connecting…")
        tk.Label(status_row, textvariable=self._conn_status_var,
                 fg="gray", font=("", 9)).pack(side=tk.RIGHT)

        self._build_aging_legend(footer)

        # Scope (left) + vertical toolbar (right)
        main_row = tk.Frame(self)
        main_row.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        center = float(self._config.get("center_khz", 14025.0))
        bw     = float(self._config.get("bandwidth_khz", 50.0))
        win    = int(self._config.get("window_minutes", 10))
        self._scope = BandScope(main_row, center_khz=center, bandwidth_khz=bw,
                                window_minutes=win, bg="white")
        self._scope.pack(side=tk.LEFT, fill=tk.Y, padx=8, pady=8)

        self._build_toolbar(main_row)

        self._refresh_aging_legend()

    def _build_toolbar(self, parent):
        toolbar = tk.Frame(parent, padx=10, pady=8)
        toolbar.pack(side=tk.LEFT, fill=tk.Y)

        def group(label_text):
            grp = tk.Frame(toolbar)
            grp.pack(side=tk.TOP, fill=tk.X, pady=(0, 12))
            tk.Label(grp, text=label_text, anchor="w").pack(side=tk.TOP, anchor="w")
            return grp

        # Center frequency
        g = group("Center kHz:")
        row = tk.Frame(g)
        row.pack(side=tk.TOP, anchor="w")
        self._center_var = tk.StringVar(value=str(self._config.get("center_khz", 14025.0)))
        centry = ttk.Entry(row, textvariable=self._center_var, width=9)
        centry.pack(side=tk.LEFT)
        centry.bind("<Return>", lambda _: self._on_set_center())
        ttk.Button(row, text="Set",
                   command=self._on_set_center).pack(side=tk.LEFT, padx=(4, 0))

        # Bandwidth
        g = group("BW kHz:")
        saved_bw = str(int(self._config.get("bandwidth_khz", 50)))
        if saved_bw not in BW_OPTIONS:
            saved_bw = "50"
        self._bw_var = tk.StringVar(value=saved_bw)
        bw_box = ttk.Combobox(g, textvariable=self._bw_var,
                               values=BW_OPTIONS, width=6, state="readonly")
        bw_box.pack(side=tk.TOP, anchor="w")
        bw_box.bind("<<ComboboxSelected>>", lambda _: self._on_set_bandwidth())

        # Window (scope history)
        g = group("Window:")
        saved_win = str(self._config.get("window_minutes", 10))
        if saved_win not in WINDOW_OPTIONS:
            saved_win = "10"
        self._window_var = tk.StringVar(value=saved_win)
        win_box = ttk.Combobox(g, textvariable=self._window_var,
                                values=WINDOW_OPTIONS, width=6, state="readonly")
        win_box.pack(side=tk.TOP, anchor="w")
        win_box.bind("<<ComboboxSelected>>", lambda _: self._on_set_window())

        # Filters button
        g = tk.Frame(toolbar)
        g.pack(side=tk.TOP, fill=tk.X, pady=(0, 12))
        ttk.Button(g, text="Filters…",
                   command=self._open_filter_panel).pack(side=tk.TOP, fill=tk.X)

    def _build_aging_legend(self, parent):
        row = tk.Frame(parent)
        row.pack(side=tk.TOP, fill=tk.X, pady=(4, 0))
        tk.Label(row, text="Aging:", fg="gray", font=("", 9)).pack(side=tk.LEFT)

        self._legend_swatches = []  # (canvas, age_minutes)
        for minutes in LEGEND_AGES_MIN:
            cell = tk.Frame(row)
            cell.pack(side=tk.LEFT, padx=(8, 0))
            canvas = tk.Canvas(cell, width=20, height=10,
                                highlightthickness=0, bg="white")
            canvas.pack(side=tk.LEFT)
            tk.Label(cell, text=f"{minutes}m", fg="gray",
                     font=("", 9)).pack(side=tk.LEFT, padx=(3, 0))
            self._legend_swatches.append((canvas, minutes))

    def _refresh_aging_legend(self):
        try:
            window_minutes = int(self._window_var.get())
        except ValueError:
            window_minutes = 10
        for canvas, age_minutes in self._legend_swatches:
            alpha = fade_alpha(age_minutes * 60, window_minutes)
            color = _blend_with_white(_NAVY, alpha)
            canvas.delete("all")
            canvas.create_line(2, 5, 18, 5, fill=color, width=2)

    # ── Connect ──────────────────────────────────────────────────────────────

    def _connect(self):
        host     = self._config.get("host",     "ve7cc.net")
        port     = self._config.get("port",     23)
        callsign = self._config.get("callsign", "N6YU")
        cf = ClusterFilter(modes=["CW"])
        self._conn = ClusterConnection(
            host, port, callsign,
            self._spot_queue,
            cluster_filter=cf,
            text_queue=self._text_queue,
        )
        self._conn.start()
        self._conn_status_var.set(f"Connected → {host}:{port}  ({callsign})")

        self._filter_panel = FilterPanel(
            self, self._conn, self._on_filter_status_change)
        self._filter_panel.withdraw()

    # ── Poll loop ────────────────────────────────────────────────────────────

    def _poll(self):
        new_spots = []
        for spot in drain_queue(self._spot_queue):
            if not self._dedup.is_dup(spot):
                self._dedup.record(spot)
                new_spots.append(spot)
        if new_spots:
            self._scope.add_spots(new_spots)
            if self._filter_panel is not None:
                for spot in new_spots:
                    self._filter_panel.append_spot_line(spot)

        if self._filter_panel is not None:
            try:
                while True:
                    line = self._text_queue.get_nowait()
                    self._filter_panel.append_server_line(line)
            except queue.Empty:
                pass

        self.after(POLL_MS, self._poll)

    # ── Control callbacks ────────────────────────────────────────────────────

    def _on_set_center(self):
        try:
            freq = float(self._center_var.get())
            self._scope.set_center(freq)
            self._config.set("center_khz", freq)
            self._config.save()
        except ValueError:
            pass

    def _on_set_bandwidth(self):
        try:
            bw = float(self._bw_var.get())
            self._scope.set_bandwidth(bw)
            self._config.set("bandwidth_khz", bw)
            self._config.save()
        except ValueError:
            pass

    def _on_set_window(self):
        try:
            minutes = int(self._window_var.get())
            self._scope.set_window(minutes)
            self._config.set("window_minutes", minutes)
            self._config.save()
            self._refresh_aging_legend()
        except ValueError:
            pass

    def _open_filter_panel(self):
        self._filter_panel.deiconify()
        self._filter_panel.lift()

    def _on_filter_status_change(self, summary: str):
        self._filter_status_var.set(summary)

    def _on_close(self):
        if self._conn:
            self._conn.stop()
        self._config.save()
        self.destroy()


if __name__ == "__main__":
    app = SpotterApp()
    app.protocol("WM_DELETE_WINDOW", app._on_close)
    app.mainloop()
