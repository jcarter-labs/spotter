import time
import tkinter as tk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter

from scope_utils import drain_queue, extract_prefix, format_freq  # noqa: F401 (re-exported)

WINDOW_MINUTES = 10
HALF_WIDTH_KHZ = 25.0
_TICK_SPACING_MIN = 2  # X-axis tick every N minutes


class BandScope(tk.Frame):
    def __init__(self, parent, center_khz: float = 14025.0, **kwargs):
        super().__init__(parent, **kwargs)
        self._center = center_khz
        self._spots = []  # list of (timestamp_float, Spot)

        self._fig = Figure(figsize=(10, 6), tight_layout=True)
        self._ax = self._fig.add_subplot(111)
        self._canvas = FigureCanvasTkAgg(self._fig, master=self)
        self._canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self._redraw()

    def set_center(self, freq_khz: float):
        self._center = freq_khz
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
        lo = self._center - HALF_WIDTH_KHZ
        hi = self._center + HALF_WIDTH_KHZ

        # X axis: T=0 (newest) on LEFT, T=-window on RIGHT — reversed xlim.
        # Y axis: frequency (kHz), higher freq at top.
        ax.set_xlabel("min", fontsize=10)
        ax.set_ylabel("Frequency (kHz)", fontsize=10)
        ax.set_title(
            f"Band Scope  {format_freq(self._center)} ± {HALF_WIDTH_KHZ:.0f} kHz",
            fontsize=11,
        )
        ax.set_xlim(now, cutoff)
        ax.set_ylim(lo, hi)

        # Elapsed-time ticks: 0, -2, -4 … -WINDOW (captured by value via default arg)
        tick_times = [now - m * 60
                      for m in range(0, WINDOW_MINUTES + 1, _TICK_SPACING_MIN)]
        ax.set_xticks(tick_times)
        ax.xaxis.set_major_formatter(
            FuncFormatter(lambda v, _, t=now: f"{int(round((v - t) / 60))}")
        )
        ax.grid(True, alpha=0.3)

        # Center-frequency hairline: blue, same visual weight as grid lines
        ax.axhline(y=self._center, color="steelblue", linewidth=0.8, alpha=0.45)

        for ts, spot in self._spots:
            if lo <= spot.freq_khz <= hi and ts >= cutoff:
                ax.plot(ts, spot.freq_khz,
                        marker="_", color="navy",
                        markersize=18, markeredgewidth=2, alpha=0.85,
                        ls="none")
                ax.annotate(
                    spot.dx_call,
                    (ts, spot.freq_khz),
                    textcoords="offset points",
                    xytext=(6, 0),
                    fontsize=7,
                    color="navy",
                    va="center",
                )

        self._canvas.draw()
