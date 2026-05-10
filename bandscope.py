import time
import tkinter as tk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter

from scope_utils import drain_queue, extract_prefix, format_freq  # noqa: F401 (re-exported)

_N_TICKS = 5


class BandScope(tk.Frame):
    def __init__(self, parent, center_khz: float = 14025.0,
                 bandwidth_khz: float = 50.0, window_minutes: int = 10,
                 **kwargs):
        super().__init__(parent, **kwargs)
        self._center  = center_khz
        self._half    = bandwidth_khz / 2.0
        self._window  = window_minutes
        self._spots   = []  # list of (timestamp_float, Spot)

        self._fig = Figure(figsize=(10, 6), tight_layout=True)
        self._ax  = self._fig.add_subplot(111)
        self._canvas = FigureCanvasTkAgg(self._fig, master=self)
        self._canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self._canvas.mpl_connect("button_press_event", self._on_click)
        self._redraw()

    def set_center(self, freq_khz: float):
        self._center = freq_khz
        self._redraw()

    def set_bandwidth(self, bandwidth_khz: float):
        self._half = bandwidth_khz / 2.0
        self._redraw()

    def set_window(self, minutes: int):
        self._window = minutes
        cutoff = time.time() - minutes * 60
        self._spots = [(t, s) for t, s in self._spots if t >= cutoff]
        self._redraw()

    def add_spots(self, spots: list):
        now = time.time()
        for spot in spots:
            self._spots.append((now, spot))
        cutoff = now - self._window * 60
        self._spots = [(t, s) for t, s in self._spots if t >= cutoff]
        self._redraw()

    def _tick_spacing_min(self):
        return self._window / _N_TICKS

    def _redraw(self):
        ax = self._ax
        ax.clear()

        now    = time.time()
        cutoff = now - self._window * 60
        lo     = self._center - self._half
        hi     = self._center + self._half

        ax.set_xlabel("min", fontsize=10)
        ax.set_ylabel("Frequency (kHz)", fontsize=10)
        ax.set_title(
            f"Band Scope  {format_freq(self._center)} ± {self._half:.0f} kHz",
            fontsize=11,
        )
        ax.set_xlim(now, cutoff)
        ax.set_ylim(lo, hi)

        spacing_min = self._tick_spacing_min()
        tick_times  = [now - i * spacing_min * 60 for i in range(_N_TICKS + 1)]
        ax.set_xticks(tick_times)
        if spacing_min >= 1:
            fmt = FuncFormatter(lambda v, _, t=now: f"{int(round((v - t) / 60))}")
        else:
            fmt = FuncFormatter(lambda v, _, t=now: f"{int(round((v - t) * 60))}s")
        ax.xaxis.set_major_formatter(fmt)
        ax.grid(True, alpha=0.3)

        # tick width = 0.8% of window so it stays visually consistent across zoom levels
        tick_sec  = self._window * 60 * 0.008
        text_x_offset = tick_sec * 0.8

        for ts, spot in self._spots:
            if lo <= spot.freq_khz <= hi and ts >= cutoff:
                # horizontal line exactly at the spot frequency
                ax.hlines(spot.freq_khz,
                          ts - tick_sec / 2, ts + tick_sec / 2,
                          colors="navy", linewidth=2, alpha=0.85, zorder=3)
                # label with vertical center on the line
                ax.text(ts + text_x_offset, spot.freq_khz,
                        spot.dx_call,
                        fontsize=7, color="navy",
                        va="center", ha="left",
                        clip_on=True, zorder=3)

        self._canvas.draw()

    def _on_click(self, event):
        if event.inaxes != self._ax or event.xdata is None:
            return
        now    = time.time()
        cutoff = now - self._window * 60
        x_range = self._window * 60 or 1
        y_range = (2 * self._half) or 1

        best, best_dist = None, float("inf")
        for ts, spot in self._spots:
            if ts < cutoff:
                continue
            dx = (event.xdata - ts) / x_range
            dy = (event.ydata - spot.freq_khz) / y_range
            d  = dx * dx + dy * dy
            if d < best_dist:
                best_dist = d
                best = spot

        if best:
            root = self.winfo_toplevel()
            root.clipboard_clear()
            root.clipboard_append(best.dx_call)
