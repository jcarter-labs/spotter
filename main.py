import queue
import tkinter as tk
from tkinter import ttk

from bandscope import BandScope
from cluster import ClusterConnection, ClusterFilter
from config import Config
from filter_panel import FilterPanel
from filters import DedupCache
from scope_utils import drain_queue

POLL_MS = 200
BW_OPTIONS    = ["10", "20", "50", "100"]
DEDUP_OPTIONS = ["1", "10", "30"]


class SpotterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("DX Spotter")
        self.geometry("1000x720")
        self.resizable(True, True)

        self._config = Config()
        self._config.load()
        self._spot_queue = queue.Queue()
        self._text_queue = queue.Queue()   # raw cluster text → filter panel
        self._dedup = DedupCache(window_minutes=self._config.get("dedup_minutes", 10))
        self._conn = None
        self._filter_panel = None

        self._build_ui()
        self._connect()
        self._poll()

    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self):
        ctrl = tk.Frame(self, pady=4)
        ctrl.pack(side=tk.TOP, fill=tk.X, padx=8)

        # Center frequency
        tk.Label(ctrl, text="Center kHz:").pack(side=tk.LEFT)
        self._center_var = tk.StringVar(value=str(self._config.get("center_khz", 14025.0)))
        centry = ttk.Entry(ctrl, textvariable=self._center_var, width=9)
        centry.pack(side=tk.LEFT, padx=(2, 0))
        centry.bind("<Return>", lambda _: self._on_set_center())
        ttk.Button(ctrl, text="Set",
                   command=self._on_set_center).pack(side=tk.LEFT, padx=(2, 10))

        # Bandwidth
        tk.Label(ctrl, text="BW kHz:").pack(side=tk.LEFT)
        saved_bw = str(int(self._config.get("bandwidth_khz", 50)))
        if saved_bw not in BW_OPTIONS:
            saved_bw = "50"
        self._bw_var = tk.StringVar(value=saved_bw)
        bw_box = ttk.Combobox(ctrl, textvariable=self._bw_var,
                               values=BW_OPTIONS, width=5, state="readonly")
        bw_box.pack(side=tk.LEFT, padx=(2, 10))
        bw_box.bind("<<ComboboxSelected>>", lambda _: self._on_set_bandwidth())

        # Dedup window
        tk.Label(ctrl, text="Dedup min:").pack(side=tk.LEFT)
        self._dedup_var = tk.StringVar(value=str(self._config.get("dedup_minutes", 10)))
        dedup_box = ttk.Combobox(ctrl, textvariable=self._dedup_var,
                                  values=DEDUP_OPTIONS, width=4)
        dedup_box.pack(side=tk.LEFT, padx=(2, 0))
        dedup_box.bind("<Return>", lambda _: self._on_set_dedup())
        dedup_box.bind("<<ComboboxSelected>>", lambda _: self._on_set_dedup())
        ttk.Button(ctrl, text="Set",
                   command=self._on_set_dedup).pack(side=tk.LEFT, padx=(2, 10))

        # Filters button
        ttk.Button(ctrl, text="Filters…",
                   command=self._open_filter_panel).pack(side=tk.LEFT, padx=(0, 6))

        # Status block (right-aligned) — connection + filter status
        status_block = tk.Frame(ctrl)
        status_block.pack(side=tk.RIGHT, padx=8)

        self._filter_status_var = tk.StringVar(value="Filters: none")
        tk.Label(status_block, textvariable=self._filter_status_var,
                 fg="#c07000", font=("", 9)).pack(anchor="e")

        self._conn_status_var = tk.StringVar(value="Connecting…")
        tk.Label(status_block, textvariable=self._conn_status_var,
                 fg="gray", font=("", 9)).pack(anchor="e")

        # Band scope
        center = float(self._config.get("center_khz", 14025.0))
        bw     = float(self._config.get("bandwidth_khz", 50.0))
        self._scope = BandScope(self, center_khz=center, bandwidth_khz=bw, bg="white")
        self._scope.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

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

        # Build filter panel now that conn exists (hidden until user opens it)
        self._filter_panel = FilterPanel(
            self, self._conn, self._on_filter_status_change)
        self._filter_panel.withdraw()

    # ── Poll loop ────────────────────────────────────────────────────────────

    def _poll(self):
        # Spots → dedup → scope
        new_spots = []
        for spot in drain_queue(self._spot_queue):
            if not self._dedup.is_dup(spot):
                self._dedup.record(spot)
                new_spots.append(spot)
        if new_spots:
            self._scope.add_spots(new_spots)

        # Cluster text → filter panel server status pane
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

    def _on_set_dedup(self):
        try:
            minutes = int(self._dedup_var.get())
            if minutes < 1:
                return
            self._dedup = DedupCache(window_minutes=minutes)
            self._config.set("dedup_minutes", minutes)
            self._config.save()
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
