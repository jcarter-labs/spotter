import time
import tkinter as tk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter

from scope_utils import drain_queue, extract_prefix, format_freq  # noqa: F401 (re-exported)

WINDOW_MINUTES = 10
_TICK_SPACING_MIN = 2


class BandScope(tk.Frame):
    def __init__(self, parent, center_khz: float = 14025.0,
                 bandwidth_khz: float = 50.0, **kwargs):
        super().__init__(parent, **kwargs)
        self._center = center_khz
        self._half = bandwidth_khz / 2.0
        self._spots = []  # list of (timestamp_float, Spot)

        self._fig = Figure(figsize=(10, 6), tight_layout=True)
        self._ax = self._fig.add_subplot(111)
        self._canvas = FigureCanvasTkAgg(self._fig, master=self)
        self._canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self._redraw()

    def set_center(self, freq_khz: float):
        self._center = freq_khz
        self._redraw()

    def set_bandwidth(self, bandwidth_khz: float):
        self._half = bandwidth_khz / 2.0
        self._redraw()

    def add_spots(self, spots: list):
        now = time.time()
        for spot in spots:
            self._spots.append((now, spot))
        cutoff = now - WINDOW_MINUTES * 60
        self._spots = [(t, s) for t, s in self._spots if t >= cutoff]
        self._redraw()

    def _redraw(self):
        ax = self._ax
        ax.clear()

        now = time.time()
        cutoff = now - WINDOW_MINUTES * 60
        lo = self._center - self._half
        hi = self._center + self._half

        ax.set_xlabel("min", fontsize=10)
        ax.set_ylabel("Frequency (kHz)", fontsize=10)
        ax.set_title(
            f"Band Scope  {format_freq(self._center)} ± {self._half:.0f} kHz",
            fontsize=11,
        )
        # X: T=0 (newest) on LEFT, T=-window on RIGHT
        ax.set_xlim(now, cutoff)
        ax.set_ylim(lo, hi)

        tick_times = [now - m * 60
                      for m in range(0, WINDOW_MINUTES + 1, _TICK_SPACING_MIN)]
        ax.set_xticks(tick_times)
        ax.xaxis.set_major_formatter(
            FuncFormatter(lambda v, _, t=now: f"{int(round((v - t) / 60))}")
        )
        ax.grid(True, alpha=0.3)

        for ts, spot in self._spots:
            if lo <= spot.freq_khz <= hi and ts >= cutoff:
                ax.plot(ts, spot.freq_khz,
                        marker="_", color="navy",
                        markersize=6, markeredgewidth=2, alpha=0.85,
                        ls="none")
                ax.annotate(
                    spot.dx_call,
                    (ts, spot.freq_khz),
                    textcoords="offset points",
                    xytext=(5, 3),
                    fontsize=7,
                    color="navy",
                    va="center",
                )

        self._canvas.draw()
