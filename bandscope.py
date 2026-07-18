import time
import tkinter as tk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.font_manager import FontProperties

from scope_utils import drain_queue, extract_prefix, format_freq  # noqa: F401 (re-exported)

_LABEL_FONTSIZE = 7
_ROW_PADDING = 1.3  # multiplier on measured text height for breathing room between stacked labels
_LEADER_THRESHOLD_PX = 1.0  # min vertical displacement before drawing a leader line
_TICK_START = 0.02  # fixed x column (axes are frequency-only; x carries no data)
_TICK_END = 0.06
_REPAINT_MS = 5000  # how often to re-fade/expire spots with no new data arriving
_FADE_FLOOR = 0.3  # alpha of a spot right at the window cutoff, just before it expires


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

        self._after_id = self.after(_REPAINT_MS, self._tick)

    def _tick(self):
        self._redraw()
        self._after_id = self.after(_REPAINT_MS, self._tick)

    def destroy(self):
        if self._after_id is not None:
            self.after_cancel(self._after_id)
            self._after_id = None
        super().destroy()

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

    def _fade_alpha(self, ts, now):
        age_frac = (now - ts) / (self._window * 60)
        return max(_FADE_FLOOR, 1.0 - age_frac * (1.0 - _FADE_FLOOR))

    def _redraw(self):
        ax = self._ax
        ax.clear()

        now    = time.time()
        cutoff = now - self._window * 60
        lo     = self._center - self._half
        hi     = self._center + self._half

        # Prune expired spots here too — this runs on a timer even when no
        # new data arrives, so this is what actually drops spots after
        # window_minutes rather than relying on the next add_spots() call.
        self._spots = [(t, s) for t, s in self._spots if t >= cutoff]

        ax.set_ylabel("Frequency (kHz)", fontsize=10)
        ax.set_title(
            f"Band Scope  {format_freq(self._center)} ± {self._half:.0f} kHz",
            fontsize=11,
        )
        ax.set_xlim(0, 1)
        ax.set_xticks([])
        ax.set_ylim(lo, hi)
        ax.grid(True, axis="y", alpha=0.3)

        visible = [(ts, spot) for ts, spot in self._spots if lo <= spot.freq_khz <= hi]

        for ts, spot in visible:
            # horizontal line exactly at the spot frequency; older spots
            # fade toward _FADE_FLOOR as they approach the window cutoff
            ax.hlines(spot.freq_khz, _TICK_START, _TICK_END,
                      colors="navy", linewidth=2,
                      alpha=0.85 * self._fade_alpha(ts, now), zorder=3)

        # First draw pass: finalizes axes layout (tight_layout, axis limits)
        # and gives us a renderer. Label placement below needs both — real
        # font-metric text widths and a live data<->pixel transform — so it
        # can't happen until after this pass.
        self._canvas.draw()
        renderer = self._canvas.get_renderer()

        # Vertical decluttering: place labels to clear each other with the
        # least total displacement from their true frequency, rather than
        # cascading a one-directional push through an entire crowded run.
        # Ticks always stay at the true frequency; only the text may move.
        # A leader line connects a label back to its tick whenever it's
        # been displaced enough to matter. Every spot sits at the same
        # fixed x column (there's no time axis anymore), so a frequency
        # gap here is a real on-screen gap — not an artifact of two spots
        # merely being close in frequency while far apart in time.
        row_height_px = self._row_height_px(renderer) * _ROW_PADDING

        items = []
        for ts, spot in sorted(visible, key=lambda item: item[1].freq_khz):
            x_disp, natural_y_disp = ax.transData.transform((_TICK_END, spot.freq_khz))
            items.append((ts, spot, x_disp, natural_y_disp))

        placed_y = self._declutter_y([it[3] for it in items], row_height_px)

        for (ts, spot, x_disp, natural_y_disp), y_disp in zip(items, placed_y):
            alpha = self._fade_alpha(ts, now)

            # gap = width of one rendered character of this label, measured
            # via actual font metrics rather than assumed — this stays
            # correct regardless of dpi/retina scaling or window/zoom level
            gap_px = self._char_width_px(spot.dx_call[0], renderer)
            x_data, y_data = ax.transData.inverted().transform((x_disp + gap_px, y_disp))

            if abs(y_disp - natural_y_disp) > _LEADER_THRESHOLD_PX:
                _, tick_y_data = ax.transData.inverted().transform((x_disp, natural_y_disp))
                ax.plot([_TICK_END, x_data], [tick_y_data, y_data],
                        color="navy", linewidth=0.6, alpha=0.5 * alpha, zorder=2)

            ax.text(x_data, y_data, spot.dx_call,
                    fontsize=_LABEL_FONTSIZE, color="navy", alpha=alpha,
                    va="center", ha="left",
                    clip_on=True, zorder=3)

        self._canvas.draw()

    def _declutter_y(self, naturals, row_height_px):
        """Place N ascending natural y-positions (pixel space) so consecutive
        placements are at least row_height_px apart, minimizing total squared
        displacement from the natural positions.

        Solved as isotonic regression on values shifted by -i*row_height_px
        (the standard reduction from a minimum-spacing constraint to a plain
        non-decreasing one), via pool-adjacent-violators: any crowded run of
        naturals gets merged into a single block and spread evenly around
        the block's average position, so displacement stays bounded by the
        run's actual spread instead of growing linearly with its length.
        """
        shifted = [y - i * row_height_px for i, y in enumerate(naturals)]

        # each block: [sum_of_values, count, start_index, end_index]
        blocks = []
        for i, v in enumerate(shifted):
            blocks.append([v, 1, i, i])
            while len(blocks) > 1 and (
                blocks[-2][0] / blocks[-2][1] > blocks[-1][0] / blocks[-1][1]
            ):
                prev = blocks.pop()
                blocks[-1][0] += prev[0]
                blocks[-1][1] += prev[1]
                blocks[-1][3] = prev[3]

        placed = [0.0] * len(naturals)
        for total, weight, start, end in blocks:
            avg = total / weight
            for i in range(start, end + 1):
                placed[i] = avg + i * row_height_px
        return placed

    def _char_width_px(self, char, renderer):
        fp = FontProperties(size=_LABEL_FONTSIZE)
        width, _height, _descent = renderer.get_text_width_height_descent(
            char, fp, ismath=False)
        return width

    def _row_height_px(self, renderer):
        fp = FontProperties(size=_LABEL_FONTSIZE)
        _width, height, _descent = renderer.get_text_width_height_descent(
            "Hg", fp, ismath=False)
        return height

    def _on_click(self, event):
        if event.inaxes != self._ax or event.ydata is None:
            return
        now    = time.time()
        cutoff = now - self._window * 60

        # There's no time axis anymore — every spot sits at the same fixed
        # x column — so the nearest spot to a click is just the closest one
        # in frequency.
        best, best_dist = None, float("inf")
        for ts, spot in self._spots:
            if ts < cutoff:
                continue
            d = abs(event.ydata - spot.freq_khz)
            if d < best_dist:
                best_dist = d
                best = spot

        if best:
            root = self.winfo_toplevel()
            root.clipboard_clear()
            root.clipboard_append(best.dx_call)
