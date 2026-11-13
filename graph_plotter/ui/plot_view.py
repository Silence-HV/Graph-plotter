"""Plot-Ansicht: Zeichenfläche, Navigation, Seitenansicht und Messfunktion."""

from __future__ import annotations

from typing import Callable, Optional

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT
from matplotlib.figure import Figure
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QGridLayout, QHBoxLayout, QLabel, QScrollArea, QSizePolicy,
                               QToolButton, QVBoxLayout, QWidget)

from . import icons, theme
from .widgets import format_number

MEASURE_GID = "measure"
CANVAS_DPI = 100  # Matplotlib-Qt: logische Pixel je Zoll


def fmt(value: float) -> str:
    return format_number(float(f"{value:.6g}"))


class _HiddenToolbar(NavigationToolbar2QT):
    """Matplotlib-Navigation ohne eigene Oberfläche (Bedienung über eigene Schaltflächen).

    Bewusst ohne „Kurven bearbeiten“: dieser Dialog baute bei Y2 die Legende falsch auf.
    """

    toolitems = [t for t in NavigationToolbar2QT.toolitems if t[0] in ("Home", "Back", "Forward", "Pan", "Zoom")]

    def set_message(self, s):  # Koordinaten zeigt die Statusleiste
        pass


class PlotView(QWidget):
    hover = Signal(str)       # Koordinaten unter dem Mauszeiger
    measured = Signal(str)    # Ergebnis der Messung
    viewChanged = Signal(bool)  # True, wenn gezoomt/verschoben (Ansicht weicht vom Plot ab)
    applyViewRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.label_lookup: Callable[[int], str] = lambda i: f"G{i + 1}"
        self._points: list[tuple[str, float, float, object]] = []
        self._home: Optional[dict] = None
        self._zoomed = False
        self._page_mode = False
        self._page_size = (16 / 2.54, 10 / 2.54)

        self.figure = Figure(figsize=(8, 6), dpi=CANVAS_DPI)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._nav = _HiddenToolbar(self.canvas, self)
        self._nav.hide()

        bar = QWidget()
        bar.setObjectName("PlotBar")
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(8, 3, 8, 3)
        bar_layout.setSpacing(2)
        self.buttons: dict[str, QToolButton] = {}
        for key, tip, checkable in (
            ("home", "Ansicht zurücksetzen", False),
            ("back", "Vorherige Ansicht", False),
            ("forward", "Nächste Ansicht", False),
            (None, None, None),
            ("pan", "Verschieben (linke Maustaste) / Zoomen (rechte Maustaste)", True),
            ("zoom", "Rechteck-Zoom", True),
            ("measure", "Messen: Messpunkte anklicken (zwei Punkte ergeben Δx/Δy), Esc löscht", True),
            ("crop", "Ausschnitt übernehmen: aktuellen Zoom als Achsengrenzen eintragen\n"
                     "(bleibt beim Neuzeichnen erhalten und wird im Projekt gespeichert)", False),
            (None, None, None),
            ("page", "Seitenansicht: Plot in Exportgröße zeigen (echte Schriftgrößen)", True),
        ):
            if key is None:
                bar_layout.addSpacing(10)
                continue
            button = QToolButton()
            button.setToolTip(tip)
            button.setCheckable(checkable)
            button.setAutoRaise(True)
            self.buttons[key] = button
            bar_layout.addWidget(button)
        bar_layout.addStretch()
        self.size_label = QLabel()
        self.size_label.setObjectName("Muted")
        bar_layout.addWidget(self.size_label)

        self.buttons["home"].clicked.connect(self._nav.home)
        self.buttons["back"].clicked.connect(self._nav.back)
        self.buttons["forward"].clicked.connect(self._nav.forward)
        self.buttons["pan"].clicked.connect(lambda: self._set_mode("pan"))
        self.buttons["zoom"].clicked.connect(lambda: self._set_mode("zoom"))
        self.buttons["measure"].clicked.connect(lambda: self._set_mode("measure"))
        self.buttons["page"].toggled.connect(self.set_page_mode)
        self.buttons["crop"].clicked.connect(self.applyViewRequested)
        self.buttons["crop"].setEnabled(False)

        self._holder = QWidget()
        self._grid = QGridLayout(self._holder)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.addWidget(self.canvas, 0, 0)
        self.area = QScrollArea()
        self.area.setObjectName("CanvasArea")
        self.area.setWidget(self._holder)
        self.area.setWidgetResizable(True)
        self._holder.setObjectName("CanvasArea")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(bar)
        layout.addWidget(self.area, 1)

        self.canvas.mpl_connect("motion_notify_event", self._on_move)
        self.canvas.mpl_connect("button_press_event", self._on_click)
        self.canvas.mpl_connect("key_press_event", self._on_key)
        self.refresh_icons()

    # ------------------------------------------------------------------ Darstellung

    def refresh_icons(self) -> None:
        color = theme.colors()["text"]
        for key, button in self.buttons.items():
            button.setIcon(icons.icon(key, color))

    def set_page_size(self, width_in: float, height_in: float) -> None:
        self._page_size = (width_in, height_in)
        self.size_label.setText(f"Export: {fmt(width_in * 2.54)} × {fmt(height_in * 2.54)} cm")
        if self._page_mode:
            self._apply_page_mode()

    def set_page_mode(self, enabled: bool) -> None:
        self._page_mode = enabled
        if self.buttons["page"].isChecked() != enabled:
            self.buttons["page"].setChecked(enabled)
        self._apply_page_mode()

    def _apply_page_mode(self) -> None:
        if self._page_mode:
            w, h = (round(v * CANVAS_DPI) for v in self._page_size)
            self.canvas.setFixedSize(w, h)
            self._grid.setContentsMargins(24, 24, 24, 24)
            self._grid.setAlignment(self.canvas, Qt.AlignmentFlag.AlignCenter)
        else:
            self.canvas.setMinimumSize(0, 0)
            self.canvas.setMaximumSize(16777215, 16777215)
            self._grid.setContentsMargins(0, 0, 0, 0)
            self._grid.setAlignment(self.canvas, Qt.AlignmentFlag(0))

    def show_message(self, text: str) -> None:
        """Leere Fläche mit Hinweistext."""
        self.figure.clear()
        self.figure.text(0.5, 0.5, text, ha="center", va="center", color="#8a8f98", fontsize=13, wrap=True)
        self.canvas.draw_idle()
        self._reset_measurement()
        self._home = None
        self._set_zoomed(False)

    def after_render(self, limits: Optional[dict] = None) -> None:
        """Nach dem Neuzeichnen: Zoom-Verlauf und Messung zurücksetzen, Ausgangsansicht merken."""
        self.canvas.draw_idle()
        self._nav.update()
        self._reset_measurement()
        self._home = dict(limits) if limits else self.view_limits()
        for ax in self.figure.axes:
            ax.callbacks.connect("xlim_changed", self._limits_changed)
            ax.callbacks.connect("ylim_changed", self._limits_changed)
        self._set_zoomed(False)

    # ------------------------------------------------------------------ Ausschnitt

    def view_limits(self) -> dict:
        """Aktuell sichtbarer Bereich: "x", "y" und ggf. "y2" -> (min, max)."""
        axes = self.figure.axes
        if not axes:
            return {}
        view = {"x": tuple(axes[0].get_xlim()), "y": tuple(axes[0].get_ylim())}
        if len(axes) > 1:
            view["y2"] = tuple(axes[1].get_ylim())
        return view

    def is_zoomed(self) -> bool:
        return self._zoomed

    def _limits_changed(self, _ax) -> None:
        if not self._home:
            return
        view = self.view_limits()
        zoomed = any(not np.allclose(view[k], self._home[k], rtol=1e-7, atol=0)
                     for k in view if k in self._home)
        self._set_zoomed(zoomed)

    def _set_zoomed(self, zoomed: bool) -> None:
        if zoomed != self._zoomed:
            self._zoomed = zoomed
            self.viewChanged.emit(zoomed)
        self.buttons["crop"].setEnabled(zoomed)

    # ------------------------------------------------------------------ Modi

    def _mode(self) -> str:
        if self.buttons["measure"].isChecked():
            return "measure"
        mode = str(self._nav.mode)
        return "pan" if "pan" in mode else "zoom" if "zoom" in mode else ""

    def _set_mode(self, wanted: str) -> None:
        current = self._mode()
        # Matplotlib-Modi sind Umschalter: aktiven Modus ausschalten, gewünschten einschalten
        if current in ("pan", "zoom"):
            getattr(self._nav, current)()
        if wanted in ("pan", "zoom") and current != wanted:
            getattr(self._nav, wanted)()
        measure = wanted == "measure" and current != "measure"
        self.buttons["measure"].setChecked(measure)
        new_mode = self._mode()
        self.buttons["pan"].setChecked(new_mode == "pan")
        self.buttons["zoom"].setChecked(new_mode == "zoom")
        self.canvas.setCursor(Qt.CursorShape.CrossCursor if measure else Qt.CursorShape.ArrowCursor)
        if not measure:
            self._reset_measurement()

    # ------------------------------------------------------------------ Maus

    def _on_move(self, event) -> None:
        axes = self.figure.axes
        if not axes or event.inaxes is None:
            self.hover.emit("")
            return
        x, y1 = axes[0].transData.inverted().transform((event.x, event.y))
        text = f"x = {fmt(x)}   y = {fmt(y1)}"
        if len(axes) > 1:
            _, y2 = axes[1].transData.inverted().transform((event.x, event.y))
            text += f"   y2 = {fmt(y2)}"
        self.hover.emit(text)

    def _nearest(self, event) -> Optional[tuple[int, float, float, object]]:
        best = None
        for ax in self.figure.axes:
            for line in ax.get_lines():
                gid = line.get_gid() or ""
                if not gid.startswith("data-") or not line.get_visible():
                    continue
                xy = np.asarray(line.get_xydata(), dtype=float)
                if not len(xy):
                    continue
                display = line.get_transform().transform(xy)
                dist = np.hypot(display[:, 0] - event.x, display[:, 1] - event.y)
                i = int(np.nanargmin(dist))
                if best is None or dist[i] < best[0]:
                    best = (dist[i], int(gid.split("-")[1]), xy[i, 0], xy[i, 1], ax)
        if best is None or best[0] > 40:  # mehr als 40 Pixel entfernt: kein Treffer
            return None
        return best[1:]

    def _on_click(self, event) -> None:
        if self._mode() != "measure" or event.button != 1 or event.inaxes is None:
            return
        hit = self._nearest(event)
        if hit is None:
            return
        index, x, y, ax = hit
        if len(self._points) >= 2:
            self._reset_measurement()
        ax.plot([x], [y], marker="o", markersize=9, markerfacecolor="none", markeredgecolor="#d00",
                markeredgewidth=2, gid=MEASURE_GID, zorder=10)
        self._points.append((self.label_lookup(index), x, y, ax))
        parts = [f"P{i + 1} {name}: x = {fmt(px)}, y = {fmt(py)}" for i, (name, px, py, _) in enumerate(self._points)]
        if len(self._points) == 2:
            (_, x1, y1, a1), (_, x2, y2, a2) = self._points
            delta = f"Δx = {fmt(x2 - x1)}"
            delta += f", Δy = {fmt(y2 - y1)}" if a1 is a2 else " (Δy nicht vergleichbar: Y1/Y2)"
            parts.append(delta)
        self.measured.emit("   │   ".join(parts))
        self.canvas.draw_idle()

    def _on_key(self, event) -> None:
        if event.key == "escape":
            self._reset_measurement()
            self.canvas.draw_idle()

    def _reset_measurement(self) -> None:
        for ax in self.figure.axes:
            for line in list(ax.get_lines()):
                if line.get_gid() == MEASURE_GID:
                    line.remove()
        if self._points:
            self._points = []
            self.measured.emit("")
