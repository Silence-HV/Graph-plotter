"""Datensätze in eine Matplotlib-Figure zeichnen (ohne Qt, dadurch testbar)."""

from __future__ import annotations

import math
import warnings
from dataclasses import asdict, dataclass, field, fields
from typing import Optional

import numpy as np
from matplotlib.figure import Figure
from matplotlib.ticker import MultipleLocator

from .fitting import FIT_KINDS, fit_curve
from .model import DEFAULT_COLORS, Dataset
from .stats import ERROR_MODES, summarize

# Anzeige-Name -> (Symbol, Faktor). Die Schlüssel sind auch in Projektdateien gespeichert.
SI_PREFIXES = {
    "p (pico)": ("p", 1e-12),
    "n (nano)": ("n", 1e-9),
    "µ (micro)": ("µ", 1e-6),
    "m (milli)": ("m", 1e-3),
    "1": ("", 1.0),
    "k (kilo)": ("k", 1e3),
    "M (mega)": ("M", 1e6),
    "G (giga)": ("G", 1e9),
}

LEGEND_LOCATIONS = {
    "best": "Automatisch",
    "upper right": "Oben rechts",
    "upper left": "Oben links",
    "lower right": "Unten rechts",
    "lower left": "Unten links",
    "outside": "Außerhalb rechts",
    "none": "Keine Legende",
}

STAT_STYLES = {"errorbar": "Fehlerbalken", "band": "Band"}

MAX_TICKS = 200
LINE_ALPHA_MULTI = 0.7


class PlotError(Exception):
    """Plot kann nicht erstellt werden (Meldung ist für Nutzer formuliert)."""


@dataclass
class AxisSettings:
    label: str = ""
    unit: str = ""
    prefix: str = "1"
    min: Optional[float] = None
    max: Optional[float] = None
    tick: Optional[float] = None
    log: bool = False


@dataclass
class PlotSettings:
    x: AxisSettings = field(default_factory=AxisSettings)
    y: AxisSettings = field(default_factory=AxisSettings)
    y2: AxisSettings = field(default_factory=AxisSettings)
    y2_enabled: bool = False
    title: str = ""
    label_fontsize: float = 30
    tick_fontsize: float = 24
    legend_fontsize: float = 30
    legend_loc: str = "best"
    grid: bool = True
    minor_ticks: bool = False
    error_mode: str = "sd"
    stat_style: str = "errorbar"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "PlotSettings":
        axis_fields = {f.name for f in fields(AxisSettings)}
        own_fields = {f.name for f in fields(cls)}
        kwargs = {}
        for key, value in data.items():
            if key not in own_fields:
                continue
            if key in ("x", "y", "y2") and isinstance(value, dict):
                value = AxisSettings(**{k: v for k, v in value.items() if k in axis_fields})
            kwargs[key] = value
        return cls(**kwargs)


@dataclass
class RenderResult:
    warnings: list[str] = field(default_factory=list)
    limits: dict = field(default_factory=dict)  # "x", "y", "y2" -> (min, max) in angezeigten Einheiten
    plotted: int = 0


def prefix_factor(key: str) -> float:
    return SI_PREFIXES.get(key, ("", 1.0))[1]


def axis_label(axis: AxisSettings, default: str) -> str:
    """Achsenbeschriftung inkl. Einheit mit SI-Präfix, z. B. „Spannung [mV]“."""
    label = axis.label.strip() or default
    symbol, factor = SI_PREFIXES.get(axis.prefix, ("", 1.0))
    unit = axis.unit.strip()
    if unit:
        return f"{label} [{symbol}{unit}]"
    if factor != 1.0:
        exponent = round(math.log10(factor))
        return f"{label} [$\\times 10^{{{exponent}}}$]"
    return label


def _apply_limits(result: RenderResult, name: str, get_lim, set_lim, lo, hi, log: bool) -> None:
    if lo is None and hi is None:
        return
    if log and ((lo is not None and lo <= 0) or (hi is not None and hi <= 0)):
        result.warnings.append(f"{name}: Grenzen müssen bei logarithmischer Achse > 0 sein – ignoriert.")
        return
    cur_lo, cur_hi = get_lim()
    new_lo = lo if lo is not None else cur_lo
    new_hi = hi if hi is not None else cur_hi
    if new_lo >= new_hi:
        result.warnings.append(f"{name}: Minimum ({new_lo:g}) muss kleiner als Maximum ({new_hi:g}) sein – ignoriert.")
        return
    set_lim(new_lo, new_hi)


def _apply_tick(result: RenderResult, name: str, axis_obj, lim, tick, log: bool) -> None:
    if tick is None:
        return
    if tick <= 0:
        result.warnings.append(f"{name}: Tick-Abstand muss größer als 0 sein – ignoriert.")
        return
    if log:
        result.warnings.append(f"{name}: Tick-Abstand wird bei logarithmischer Achse ignoriert.")
        return
    count = abs(lim[1] - lim[0]) / tick
    if count > MAX_TICKS:
        result.warnings.append(
            f"{name}: Tick-Abstand {tick:g} ergäbe {count:,.0f} Markierungen (max. {MAX_TICKS}) – ignoriert."
            .replace(",", "."))
        return
    axis_obj.set_major_locator(MultipleLocator(tick))


def render(fig: Figure, datasets: list[Dataset], settings: PlotSettings,
           rasterize: bool = False) -> RenderResult:
    """Alle sichtbaren Datensätze zeichnen.

    Args:
        rasterize: Datenlinien als Pixelbild einbetten (kleinere PDF/SVG-Dateien bei vielen Punkten).

    Raises:
        PlotError: wenn nichts gezeichnet werden kann.
    """
    visible = [(i, d) for i, d in enumerate(datasets) if d.visible]
    if not visible:
        raise PlotError("Keine sichtbaren Datensätze vorhanden.")

    result = RenderResult()
    fig.clear()
    ax = fig.add_subplot(111)
    ax2 = ax.twinx() if settings.y2_enabled else None

    if settings.x.log:
        ax.set_xscale("log")
    if settings.y.log:
        ax.set_yscale("log")
    if ax2 is not None and settings.y2.log:
        ax2.set_yscale("log")

    x_factor = prefix_factor(settings.x.prefix)
    alpha = LINE_ALPHA_MULTI if len(visible) > 1 else 1.0
    handles = []
    any_statistics = False

    for index, ds in visible:
        use_y2 = ax2 is not None and ds.axis == "Y2"
        target = ax2 if use_y2 else ax
        y_axis = settings.y2 if use_y2 else settings.y
        y_factor = prefix_factor(y_axis.prefix)

        x = np.asarray(ds.x, dtype=float) / x_factor
        err = None
        if ds.is_statistics:
            mean, err, _ = summarize(ds.y_raw, settings.error_mode)
            y = mean / y_factor
            err = err / y_factor
            any_statistics = True
        else:
            y = np.asarray(ds.y, dtype=float) / y_factor

        mask = np.isfinite(x) & np.isfinite(y)
        if settings.x.min is not None:
            mask &= x >= settings.x.min
        if settings.x.max is not None:
            mask &= x <= settings.x.max
        if settings.x.log:
            mask &= x > 0
        if y_axis.log:
            mask &= y > 0
        if not mask.any():
            result.warnings.append(f"„{ds.display_label}“: keine Datenpunkte im gewählten Bereich.")
            continue

        x, y = x[mask], y[mask]
        if err is not None:
            err = np.nan_to_num(err[mask], nan=0.0)

        color = ds.color or DEFAULT_COLORS[index % len(DEFAULT_COLORS)]
        suffixes = []
        if ds.is_statistics:
            suffixes.append(f"Mittelwert ± {ERROR_MODES[settings.error_mode]}")
        if use_y2:
            suffixes.append("Y2")
        legend_label = ds.display_label + (f" ({', '.join(suffixes)})" if suffixes else "")

        if err is not None:
            if settings.stat_style == "band":
                target.fill_between(x, y - err, y + err, color=color, alpha=0.25 * alpha,
                                    linewidth=0, rasterized=rasterize)
            else:
                target.errorbar(x, y, yerr=err, fmt="none", ecolor=color, elinewidth=1.2,
                                capsize=3, capthick=1.2, alpha=alpha, rasterized=rasterize)

        draw_line = ds.draw != "marker"
        draw_marker = ds.draw != "line"
        line, = target.plot(
            x, y,
            color=color,
            linestyle=ds.linestyle if draw_line else "none",
            linewidth=ds.linewidth,
            marker=ds.marker if draw_marker else "None",
            markersize=ds.markersize,
            markerfacecolor=color if ds.marker_filled else "white",
            markeredgecolor=color,
            alpha=alpha,
            label=legend_label,
            rasterized=rasterize,
        )
        handles.append(line)
        result.plotted += 1

        if ds.fit and ds.fit != "none":
            try:
                fit = fit_curve(x, y, ds.fit)
            except ValueError as exc:
                result.warnings.append(f"Fit ({FIT_KINDS.get(ds.fit, ds.fit)}) für „{ds.display_label}“: {exc}.")
            else:
                if settings.x.log and x.min() > 0:
                    xs = np.geomspace(x.min(), x.max(), 400)
                else:
                    xs = np.linspace(x.min(), x.max(), 400)
                fit_line, = target.plot(xs, fit.predict(xs), color=color, linestyle=":",
                                        linewidth=max(1.5, ds.linewidth),
                                        label=f"Fit: {fit.equation}, R² = {fit.r2:.4f}",
                                        rasterized=rasterize)
                handles.append(fit_line)

    if result.plotted == 0:
        raise PlotError("Keine Datenpunkte innerhalb der gesetzten Grenzen.\n" + "\n".join(result.warnings))

    # Beschriftung
    label_fs = settings.label_fontsize
    tick_fs = settings.tick_fontsize
    ax.set_xlabel(axis_label(settings.x, "Zeit"), fontsize=label_fs, fontweight="bold")
    ax.set_ylabel(axis_label(settings.y, "Wert"), fontsize=label_fs, fontweight="bold")
    if settings.title.strip():
        ax.set_title(settings.title.strip(), fontsize=label_fs, fontweight="bold")
    ax.tick_params(axis="both", which="major", labelsize=tick_fs)
    ax.xaxis.get_offset_text().set_fontsize(tick_fs)
    ax.yaxis.get_offset_text().set_fontsize(tick_fs)
    if ax2 is not None:
        ax2.set_ylabel(axis_label(settings.y2, "Wert 2"), fontsize=label_fs, fontweight="bold")
        ax2.tick_params(axis="y", which="major", labelsize=tick_fs)
        ax2.yaxis.get_offset_text().set_fontsize(tick_fs)

    # Grenzen (jede Y-Achse wird nur aus ihren eigenen Datensätzen autoskaliert)
    _apply_limits(result, "X-Achse", ax.get_xlim, ax.set_xlim, settings.x.min, settings.x.max, settings.x.log)
    _apply_limits(result, "Y-Achse", ax.get_ylim, ax.set_ylim, settings.y.min, settings.y.max, settings.y.log)
    if ax2 is not None:
        _apply_limits(result, "Y2-Achse", ax2.get_ylim, ax2.set_ylim,
                      settings.y2.min, settings.y2.max, settings.y2.log)

    # Ticks
    _apply_tick(result, "X-Achse", ax.xaxis, ax.get_xlim(), settings.x.tick, settings.x.log)
    _apply_tick(result, "Y-Achse", ax.yaxis, ax.get_ylim(), settings.y.tick, settings.y.log)
    if ax2 is not None:
        _apply_tick(result, "Y2-Achse", ax2.yaxis, ax2.get_ylim(), settings.y2.tick, settings.y2.log)

    if settings.minor_ticks:
        ax.minorticks_on()
        if ax2 is not None:
            ax2.minorticks_on()
    if settings.grid:
        ax.grid(True, which="major", alpha=0.3)
        if settings.minor_ticks:
            ax.grid(True, which="minor", alpha=0.1)

    # Legende (auf der obersten Achse, damit sie nicht von Y2-Linien verdeckt wird)
    has_custom_label = any(d.label.strip() for _, d in visible)
    show_legend = settings.legend_loc != "none" and (
        len(handles) > 1 or any_statistics or ax2 is not None or has_custom_label)
    if show_legend:
        legend_ax = ax2 if ax2 is not None else ax
        labels = [h.get_label() for h in handles]
        if settings.legend_loc == "outside":
            # Bei Y2 rechts genug Platz für die Y2-Beschriftung lassen
            anchor_x = 1.25 if ax2 is not None else 1.02
            legend_ax.legend(handles, labels, loc="upper left", bbox_to_anchor=(anchor_x, 1.0),
                             borderaxespad=0.0, fontsize=settings.legend_fontsize)
        else:
            legend_ax.legend(handles, labels, loc=settings.legend_loc, fontsize=settings.legend_fontsize)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        try:
            fig.tight_layout()
        except (ValueError, RuntimeError):
            pass

    result.limits["x"] = tuple(ax.get_xlim())
    result.limits["y"] = tuple(ax.get_ylim())
    if ax2 is not None:
        result.limits["y2"] = tuple(ax2.get_ylim())
    return result
