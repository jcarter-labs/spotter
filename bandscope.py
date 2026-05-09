import time
import tkinter as tk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter

from scope_utils import drain_queue, extract_prefix, format_freq  # noqa: F401 (re-exported)

WINDOW_MINUTES = 30
HALF_WIDTH_KHZ = 25.0


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

        ax.set_xlabel("Frequency (kHz)", fontsize=10)
        ax.set_ylabel("Time (UTC)", fontsize=10)
        ax.set_title(
            f"Band Scope  {format_freq(self._center)} ± {HALF_WIDTH_KHZ:.0f} kHz",
            fontsize=11,
        )
        ax.set_xlim(lo, hi)
        ax.set_ylim(cutoff, now)
        ax.yaxis.set_major_formatter(
            FuncFormatter(lambda v, _: time.strftime("%H:%Mz", time.gmtime(v)))
        )
        ax.grid(True, alpha=0.3)

        # Center frequency reference line
        ax.axvline(x=self._center, color="red", linewidth=0.8, alpha=0.5, linestyle="--")

        for ts, spot in self._spots:
            if lo <= spot.freq_khz <= hi and ts >= cutoff:
                ax.plot(spot.freq_khz, ts, "b^", markersize=9, alpha=0.8,
                        markeredgecolor="navy", markeredgewidth=0.5)
                ax.annotate(
                    spot.dx_call,
                    (spot.freq_khz, ts),
                    textcoords="offset points",
                    xytext=(5, 2),
                    fontsize=7,
                    color="navy",
                )

        self._canvas.draw()
