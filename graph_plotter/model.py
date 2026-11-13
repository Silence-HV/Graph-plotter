"""Datenmodell: Import-Einstellungen und Datensätze mit ihren Darstellungsoptionen."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from typing import Optional

import numpy as np

# Farbenblind-taugliche Standardpalette (matplotlib "tab10")
DEFAULT_COLORS = [
    "#1f77b4", "#d62728", "#2ca02c", "#ff7f0e", "#9467bd",
    "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
]

DRAW_MODES = {"line+marker": "Linie + Marker", "line": "Nur Linie", "marker": "Nur Marker"}
LINESTYLES = {"-": "Durchgezogen", "--": "Gestrichelt", ":": "Gepunktet", "-.": "Strich-Punkt"}
MARKERS = {"o": "Kreis", "s": "Quadrat", "^": "Dreieck", "D": "Raute", "x": "Kreuz", "+": "Plus", ".": "Punkt"}


@dataclass
class ImportSpec:
    """Beschreibt vollständig, wie Datensätze aus einer Datei gelesen werden.

    Zeilen- und Spaltennummern sind 0-basiert.
    """

    path: str
    sheet: Optional[str] = None          # Excel-Tabellenblatt (None = aktives Blatt)
    header_row: Optional[int] = None     # Zeile mit Spaltennamen (None = keine Kopfzeile)
    data_start: int = 0                  # erste Zeile mit Messwerten
    x_col: int = 0
    y_cols: list[int] = field(default_factory=list)  # leer = alle Spalten außer X
    statistics: bool = False             # Y-Spalten als Messwiederholungen zusammenfassen
    sort_x: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ImportSpec":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})


_STYLE_FIELDS = ("label", "color", "axis", "visible", "draw", "linestyle",
                 "linewidth", "marker", "markersize", "marker_filled", "fit")


@dataclass
class Dataset:
    """Ein darstellbarer Datensatz.

    Standard-Datensatz: ``y`` enthält die Werte.
    Statistik-Datensatz: ``y_raw`` enthält alle Messwiederholungen (Form: Messungen × Punkte);
    Mittelwert und Fehlermaß werden erst beim Zeichnen berechnet.
    """

    name: str
    x: np.ndarray
    y: Optional[np.ndarray] = None
    y_raw: Optional[np.ndarray] = None
    spec: Optional[ImportSpec] = None
    source_column: str = ""

    # Darstellung
    label: str = ""                # eigener Legendentext (leer = name)
    color: Optional[str] = None
    axis: str = "Y1"
    visible: bool = True
    draw: str = "line+marker"
    linestyle: str = "-"
    linewidth: float = 2.0
    marker: str = "o"
    markersize: float = 4.0
    marker_filled: bool = True
    fit: str = "none"

    @property
    def is_statistics(self) -> bool:
        return self.y_raw is not None

    @property
    def display_label(self) -> str:
        return self.label.strip() or self.name

    @property
    def n_points(self) -> int:
        return int(len(self.x))

    @property
    def n_repeats(self) -> int:
        return int(self.y_raw.shape[0]) if self.y_raw is not None else 1

    def style_dict(self) -> dict:
        return {name: getattr(self, name) for name in _STYLE_FIELDS}

    def apply_style(self, style: dict) -> None:
        for name in _STYLE_FIELDS:
            if name in style:
                setattr(self, name, style[name])
