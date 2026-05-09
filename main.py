import queue
import tkinter as tk
from tkinter import ttk

from bandscope import BandScope
from scope_utils import drain_queue
from cluster import ClusterConnection, ClusterFilter
from config import Config
from filters import DedupCache

POLL_MS = 200


class SpotterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("DX Spotter")
        self.geometry("1000x680")
        self.resizable(True, True)

        self._config = Config()
        self._config.load()
        self._spot_queue = queue.Queue()
        self._dedup = DedupCache(window_minutes=self._config.get("dedup_minutes", 10))
        self._conn = None

        self._build_ui()
        self._connect()
        self._poll()

    def _build_ui(self):
        ctrl = tk.Frame(self, pady=4)
        ctrl.pack(side=tk.TOP, fill=tk.X, padx=8)

        tk.Label(ctrl, text="Center kHz:").pack(side=tk.LEFT)
        self._center_var = tk.StringVar(value=str(self._config.get("center_khz", 14025.0)))
        entry = ttk.Entry(ctrl, textvariable=self._center_var, width=10)
        entry.pack(side=tk.LEFT, padx=4)
        entry.bind("<Return>", lambda _: self._on_set_center())
        ttk.Button(ctrl, text="Set", command=self._on_set_center).pack(side=tk.LEFT)

        self._status_var = tk.StringVar(value="Connecting…")
        tk.Label(ctrl, textvariable=self._status_var, fg="gray", anchor="e").pack(
            side=tk.RIGHT, padx=8
        )

        center = float(self._config.get("center_khz", 14025.0))
        self._scope = BandScope(self, center_khz=center, bg="white")
        self._scope.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

    def _connect(self):
        host = self._config.get("host", "ve7cc.net")
        port = self._config.get("port", 23)
        callsign = self._config.get("callsign", "N6YU")
        cf = ClusterFilter(modes=["CW"])
        self._conn = ClusterConnection(host, port, callsign, self._spot_queue,
                                       cluster_filter=cf)
        self._conn.start()
        self._status_var.set(f"Connected → {host}:{port}  ({callsign})")

    def _poll(self):
        new_spots = []
        for spot in drain_queue(self._spot_queue):
            if not self._dedup.is_dup(spot):
                self._dedup.record(spot)
                new_spots.append(spot)
        if new_spots:
            self._scope.add_spots(new_spots)
        self.after(POLL_MS, self._poll)

    def _on_set_center(self):
        try:
            freq = float(self._center_var.get())
            self._scope.set_center(freq)
            self._config.set("center_khz", freq)
            self._config.save()
        except ValueError:
            pass

    def _on_close(self):
        if self._conn:
            self._conn.stop()
        self._config.save()
        self.destroy()


if __name__ == "__main__":
    app = SpotterApp()
    app.protocol("WM_DELETE_WINDOW", app._on_close)
    app.mainloop()
