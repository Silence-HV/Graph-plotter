"""Optisch verlustfreie Datenreduktion für den Export.

Hintergrund: In Vektorformaten (SVG, PDF) wird jeder Marker und jeder Fehlerbalken als eigenes
Objekt gespeichert. Bei hunderttausenden Messpunkten entstehen Dateien, die Word, Inkscape oder
PDF-Viewer kaum noch darstellen können. Mehr Punkte als Pixel in der Ausgabe kann man ohnehin
nicht sehen – die Funktionen hier entfernen genau diese unsichtbaren Punkte.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass
class Reduction:
    """Einstellungen für die Reduktion beim Export."""

    width_px: int                 # Breite der Ausgabe in Pixeln (bei der Export-Auflösung)
    height_px: int
    dpi: float
    lines: bool = True            # Linien/Bänder auf Min/Max je Pixelspalte reduzieren
    thin_markers: bool = True     # Marker und Fehlerbalken begrenzen
    marker_limit: int = 250       # max. Marker/Fehlerbalken je Datensatz (Linie + Marker)


def _bin_index(x: np.ndarray, n_bins: int, log: bool) -> np.ndarray | None:
    """Pixelspalte je Punkt; None, wenn nicht sinnvoll reduzierbar (unsortiert, ohne Ausdehnung)."""
    if len(x) < 2 or np.any(np.diff(x) < 0):
        return None
    xs = np.log10(x) if log else x
    span = xs[-1] - xs[0]
    if not np.isfinite(span) or span <= 0:
        return None
    return np.minimum(((xs - xs[0]) / span * n_bins).astype(np.int64), n_bins - 1)


def _segments(bins: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    starts = np.flatnonzero(np.r_[True, bins[1:] != bins[:-1]])
    ends = np.r_[starts[1:], len(bins)] - 1
    return starts, ends


def minmax_reduce(x, y, n_bins: int, log: bool = False) -> tuple[np.ndarray, np.ndarray]:
    """Linie auf erster/kleinster/größter/letzter Punkt je X-Intervall reduzieren (M4-Verfahren).

    Bei ``n_bins`` = Pixelbreite ist das Ergebnis optisch nicht vom Original zu unterscheiden:
    Spitzen und Ausreißer bleiben erhalten. Unsortierte X-Werte werden nicht reduziert, weil die
    Linie dann hin und her springt.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if n_bins < 1 or len(x) <= 4 * n_bins:
        return x, y
    bins = _bin_index(x, n_bins, log)
    if bins is None:
        return x, y
    starts, ends = _segments(bins)
    segment = np.repeat(np.arange(len(starts)), ends - starts + 1)
    # Nach Segment, darin nach y sortiert: erstes Element = Minimum, letztes = Maximum.
    order = np.lexsort((y, segment))
    keep = np.unique(np.concatenate([starts, ends, order[starts], order[ends]]))
    return x[keep], y[keep]


def band_reduce(x, lower, upper, n_bins: int, log: bool = False):
    """Fehlerband auf die Hüllkurve je X-Intervall reduzieren (kleinstes Unten, größtes Oben)."""
    x = np.asarray(x, dtype=float)
    lower = np.asarray(lower, dtype=float)
    upper = np.asarray(upper, dtype=float)
    if n_bins < 1 or len(x) <= 2 * n_bins:
        return x, lower, upper
    bins = _bin_index(x, n_bins, log)
    if bins is None:
        return x, lower, upper
    starts, ends = _segments(bins)
    lo = np.minimum.reduceat(lower, starts)
    hi = np.maximum.reduceat(upper, starts)
    xs = np.column_stack([x[starts], x[ends]]).ravel()
    return xs, np.repeat(lo, 2), np.repeat(hi, 2)


def dedupe_markers(x, y, x_range, y_range, width_px: int, height_px: int, cell_px: float,
                   x_log: bool = False, y_log: bool = False) -> np.ndarray:
    """Indizes der Marker, die nach Zusammenfassen deckungsgleicher Marker übrig bleiben.

    Alle Marker, die in dieselbe Zelle von ``cell_px`` Pixeln fallen, werden durch einen ersetzt.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if len(x) == 0:
        return np.arange(0)

    def scaled(values, value_range, log, size_px):
        lo, hi = value_range
        if log:
            values, lo, hi = np.log10(values), math.log10(lo), math.log10(hi)
        span = hi - lo
        if not np.isfinite(span) or span <= 0:
            return np.zeros(len(values), dtype=np.int64)
        return np.floor((values - lo) / span * size_px / cell_px).astype(np.int64)

    cx = scaled(x, x_range, x_log, width_px)
    cy = scaled(y, y_range, y_log, height_px)
    cy = cy - cy.min()
    key = (cx - cx.min()) * (int(cy.max()) + 1) + cy
    _, first = np.unique(key, return_index=True)
    return np.sort(first)


def thinning_step(n_points: int, limit: int) -> int:
    """Jeder wievielte Punkt einen Marker/Fehlerbalken bekommt (1 = alle)."""
    if limit < 1 or n_points <= limit:
        return 1
    return int(math.ceil(n_points / limit))
