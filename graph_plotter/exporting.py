"""Plot als Datei exportieren (ohne Qt, dadurch testbar)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib
from matplotlib.figure import Figure

from .model import Dataset
from .plotting import PlotSettings, RenderResult, export_rc, render
from .reduction import Reduction

# Endung -> (Beschreibung, Vektorformat)
FORMATS = {
    "pdf": ("PDF – Vektor", True),
    "svg": ("SVG – Vektor", True),
    "svgz": ("SVGZ – komprimiertes SVG", True),
    "eps": ("EPS – Vektor (LaTeX, ältere Programme)", True),
    "png": ("PNG – Rasterbild, verlustfrei", False),
    "jpg": ("JPEG – komprimiertes Rasterbild", False),
    "tiff": ("TIFF – Rasterbild, LZW-komprimiert", False),
    "webp": ("WebP – Rasterbild", False),
}


@dataclass
class ExportOptions:
    width_in: float
    height_in: float
    dpi: int = 300
    reduce_data: bool = True      # optisch verlustfreie Min/Max-Reduktion der Linien
    thin_markers: bool = True     # Marker/Fehlerbalken begrenzen (nur Vektorformate)
    marker_limit: int = 250
    editable_text: bool = True    # Text als Schrift statt als Pfade (nur Vektorformate)
    rasterize: bool = False       # Datenlinien als Bild einbetten (Notlösung)


def normalize_extension(path: str) -> str:
    ext = Path(path).suffix.lower().lstrip(".")
    return {"jpeg": "jpg", "tif": "tiff"}.get(ext, ext)


def is_vector(ext: str) -> bool:
    return FORMATS.get(ext, ("", False))[1]


def export_plot(path: str, datasets: list[Dataset], settings: PlotSettings,
                options: ExportOptions) -> RenderResult:
    """Plot neu (mit fester Größe) zeichnen und speichern.

    Raises:
        PlotError, OSError, ValueError
    """
    ext = normalize_extension(path)
    if ext not in FORMATS:
        raise ValueError(f"Unbekanntes Dateiformat: .{ext}")
    vector = is_vector(ext)

    reduction = None
    if options.reduce_data or (vector and options.thin_markers):
        reduction = Reduction(
            width_px=max(1, int(options.width_in * options.dpi)),
            height_px=max(1, int(options.height_in * options.dpi)),
            dpi=options.dpi,
            lines=options.reduce_data,
            thin_markers=vector and options.thin_markers,
            marker_limit=options.marker_limit,
        )

    kwargs: dict = {"format": {"jpg": "jpeg"}.get(ext, ext), "dpi": options.dpi}
    if settings.legend_loc == "outside":
        kwargs["bbox_inches"] = "tight"  # Legende außerhalb muss mit aufs Bild
    if ext == "png":
        kwargs["pil_kwargs"] = {"optimize": True, "compress_level": 9}
    elif ext == "jpg":
        kwargs["pil_kwargs"] = {"optimize": True, "quality": 95}
    elif ext == "tiff":
        kwargs["pil_kwargs"] = {"compression": "tiff_lzw"}
    elif ext == "webp":
        kwargs["pil_kwargs"] = {"quality": 95}
    elif ext in ("svg", "svgz"):
        kwargs["metadata"] = {"Creator": None, "Date": None, "Format": None, "Type": None}
    elif ext == "pdf":
        kwargs["metadata"] = {"Creator": "Graph Plotter", "Producer": None}

    with matplotlib.rc_context(export_rc(vector and options.editable_text)):
        figure = Figure(figsize=(options.width_in, options.height_in), dpi=100)
        result = render(figure, datasets, settings,
                        rasterize=vector and options.rasterize, reduction=reduction)
        figure.savefig(path, **kwargs)
    return result
