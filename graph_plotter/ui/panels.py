"""Eigenschaften-Tabs der rechten Seitenleiste."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QHBoxLayout, QLabel,
                               QLineEdit, QScrollArea, QSpinBox, QVBoxLayout, QWidget)

from ..fitting import FIT_KINDS
from ..model import DEFAULT_COLORS, DRAW_MODES, LINESTYLES, MARKERS, Dataset
from ..plotting import LEGEND_LOCATIONS, STAT_STYLES, AxisSettings, ExportSettings, PlotSettings
from ..stats import ERROR_MODE_NAMES
from .widgets import AxisEditor, ColorButton, Section, fill_combo, form_layout, set_combo


def scrollable(widget: QWidget) -> QScrollArea:
    area = QScrollArea()
    area.setWidget(widget)
    area.setWidgetResizable(True)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    return area


def _muted(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("Muted")
    label.setWordWrap(True)
    return label


class DatasetEditor(QWidget):
    """Darstellung der ausgewählten Datensätze. Änderungen gelten für alle ausgewählten."""

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._targets: list[Dataset] = []
        self._loading = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        self.hint = _muted("Links einen oder mehrere Datensätze auswählen, um Legende, Farbe, "
                           "Linie, Marker und Kurvenanpassung festzulegen.")
        layout.addWidget(self.hint)

        self.body = QWidget()
        body = QVBoxLayout(self.body)
        body.setContentsMargins(0, 0, 0, 0)
        self.title = QLabel()
        self.title.setWordWrap(True)
        self.title.setStyleSheet("font-weight: 600; font-size: 11pt;")
        self.info = _muted("")
        body.addWidget(self.title)
        body.addWidget(self.info)

        general = QWidget()
        form = form_layout()
        general.setLayout(form)
        self.label_edit = QLineEdit()
        self.color = ColorButton()
        self.axis = QComboBox()
        self.axis.addItem("Y1 (links)", "Y1")
        self.axis.addItem("Y2 (rechts)", "Y2")
        self.axis.setToolTip("Y2 muss unter „Achsen“ aktiviert sein.")
        form.addRow("Legende", self.label_edit)
        form.addRow("Farbe", self.color)
        form.addRow("Achse", self.axis)
        body.addWidget(Section("Allgemein", general))

        style = QWidget()
        form = form_layout()
        style.setLayout(form)
        self.draw = fill_combo(QComboBox(), DRAW_MODES)
        self.linestyle = fill_combo(QComboBox(), LINESTYLES)
        self.linewidth = QDoubleSpinBox()
        self.linewidth.setRange(0.2, 10)
        self.linewidth.setSingleStep(0.5)
        self.marker = fill_combo(QComboBox(), MARKERS)
        self.markersize = QDoubleSpinBox()
        self.markersize.setRange(1, 30)
        self.filled = QCheckBox("Marker gefüllt")
        form.addRow("Darstellung", self.draw)
        form.addRow("Linienstil", self.linestyle)
        form.addRow("Linienbreite", self.linewidth)
        form.addRow("Marker", self.marker)
        form.addRow("Markergröße", self.markersize)
        form.addRow("", self.filled)
        body.addWidget(Section("Linie und Marker", style))

        fit = QWidget()
        form = form_layout()
        fit.setLayout(form)
        self.fit = fill_combo(QComboBox(), FIT_KINDS)
        form.addRow("Fit", self.fit)
        form.addRow(_muted("Die Anpassung erfolgt in den angezeigten Einheiten über die sichtbaren "
                           "Punkte. Gleichung und R² erscheinen in der Legende."))
        body.addWidget(Section("Kurvenanpassung", fit))
        body.addStretch()
        layout.addWidget(self.body)
        layout.addStretch()

        self.label_edit.textChanged.connect(lambda t: self._set("label", t, only_first=True))
        self.color.colorChanged.connect(lambda c: self._set("color", c))
        self.axis.currentIndexChanged.connect(lambda _: self._set("axis", self.axis.currentData()))
        self.draw.currentIndexChanged.connect(lambda _: self._set("draw", self.draw.currentData()))
        self.linestyle.currentIndexChanged.connect(lambda _: self._set("linestyle", self.linestyle.currentData()))
        self.linewidth.valueChanged.connect(lambda v: self._set("linewidth", v))
        self.marker.currentIndexChanged.connect(lambda _: self._set("marker", self.marker.currentData()))
        self.markersize.valueChanged.connect(lambda v: self._set("markersize", v))
        self.filled.toggled.connect(lambda v: self._set("marker_filled", v))
        self.fit.currentIndexChanged.connect(lambda _: self._set("fit", self.fit.currentData()))
        self.set_targets([])

    def set_targets(self, datasets: list[Dataset], colors: list[str] | None = None) -> None:
        self._targets = list(datasets)
        has = bool(datasets)
        self.hint.setVisible(not has)
        self.body.setVisible(has)
        if not has:
            return
        first = datasets[0]
        self._loading = True
        if len(datasets) == 1:
            self.title.setText(first.display_label)
            info = [f"{first.n_points:,} Punkte".replace(",", ".")]
            if first.is_combined:
                info.append(f"Mittelwert aus {first.n_repeats} Messreihen von {len(first.members)} Datensätzen")
            elif first.is_statistics:
                info.append(f"Mittelwert aus {first.n_repeats} Messwiederholungen")
            if first.spec is not None:
                info.append(first.spec.path)
            self.info.setText("\n".join(info))
        else:
            self.title.setText(f"{len(datasets)} Datensätze ausgewählt")
            self.info.setText("Änderungen gelten für alle ausgewählten Datensätze.")
        self.label_edit.setEnabled(len(datasets) == 1)
        self.label_edit.setText(first.label if len(datasets) == 1 else "")
        self.label_edit.setPlaceholderText(first.name if len(datasets) == 1 else "nur bei einem Datensatz")
        self.color.set_color((colors[0] if colors else None) or first.color or DEFAULT_COLORS[0])
        set_combo(self.axis, first.axis)
        set_combo(self.draw, first.draw)
        set_combo(self.linestyle, first.linestyle)
        self.linewidth.setValue(first.linewidth)
        set_combo(self.marker, first.marker)
        self.markersize.setValue(first.markersize)
        self.filled.setChecked(first.marker_filled)
        set_combo(self.fit, first.fit)
        self._loading = False

    def _set(self, name: str, value, only_first: bool = False) -> None:
        if self._loading or not self._targets:
            return
        for ds in self._targets[:1] if only_first else self._targets:
            setattr(ds, name, value)
        if name == "label" and len(self._targets) == 1:
            self.title.setText(self._targets[0].display_label)
        self.changed.emit()


class AxesPanel(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 10)
        self.x = AxisEditor("X-Achse", "Zeit", "z. B. s")
        self.y = AxisEditor("Y-Achse", "Wert", "z. B. V, m/s²")
        self.y2 = AxisEditor("Y2-Achse", "Wert 2", "z. B. °C")
        self.y2_check = QCheckBox("Sekundäre Y-Achse (rechts) verwenden")
        self.y2_check.setToolTip("Datensätze werden im Tab „Datensatz“ der Achse Y2 zugeordnet.")

        y2_box = QWidget()
        y2_layout = QVBoxLayout(y2_box)
        y2_layout.setContentsMargins(0, 0, 0, 0)
        y2_layout.addWidget(self.y2_check)
        y2_layout.addWidget(self.y2)

        layout.addWidget(Section("X-Achse", self.x))
        layout.addWidget(Section("Y-Achse", self.y))
        layout.addWidget(Section("Y2-Achse", y2_box, expanded=False))
        layout.addStretch()

        for editor in (self.x, self.y, self.y2):
            editor.changed.connect(self.changed)
        self.y2_check.toggled.connect(self._y2_toggled)
        self._y2_toggled(False)

    def _y2_toggled(self, enabled: bool) -> None:
        self.y2.setEnabled(enabled)
        self.changed.emit()

    def axes(self) -> tuple[AxisSettings, AxisSettings, AxisSettings]:
        """Raises ValueError mit allen ungültigen Feldern."""
        errors, result = [], []
        for editor, needed in ((self.x, True), (self.y, True), (self.y2, self.y2_check.isChecked())):
            try:
                result.append(editor.settings())
            except ValueError as exc:
                if needed:
                    errors.append(str(exc))
                result.append(AxisSettings())
        if errors:
            raise ValueError("\n".join(errors))
        return tuple(result)

    def set_axes(self, s: PlotSettings) -> None:
        self.x.set_settings(s.x)
        self.y.set_settings(s.y)
        self.y2.set_settings(s.y2)
        self.y2_check.setChecked(s.y2_enabled)

    def set_auto(self, limits: dict) -> None:
        self.x.set_auto(limits.get("x"))
        self.y.set_auto(limits.get("y"))
        self.y2.set_auto(limits.get("y2"))


class AppearancePanel(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 10)

        text = QWidget()
        form = form_layout()
        text.setLayout(form)
        self.title = QLineEdit()
        self.title.setPlaceholderText("optional")
        self.label_size = self._size(14)
        self.tick_size = self._size(12)
        self.legend_size = self._size(12)
        form.addRow("Titel", self.title)
        form.addRow("Achsenbeschriftung", self.label_size)
        form.addRow("Tick-Beschriftung", self.tick_size)
        form.addRow("Legende", self.legend_size)
        form.addRow(_muted("Schriftgrößen in Punkt – sie beziehen sich auf die Exportgröße. "
                           "Die Seitenansicht (Blatt-Symbol über dem Plot) zeigt das echte "
                           "Größenverhältnis."))
        layout.addWidget(Section("Text", text))

        layout_box = QWidget()
        form = form_layout()
        layout_box.setLayout(form)
        self.legend = fill_combo(QComboBox(), LEGEND_LOCATIONS)
        self.grid = QCheckBox("Raster")
        self.grid.setChecked(True)
        self.minor = QCheckBox("Nebenticks")
        checks = QHBoxLayout()
        checks.addWidget(self.grid)
        checks.addWidget(self.minor)
        checks.addStretch()
        form.addRow("Legende", self.legend)
        form.addRow("", checks)
        layout.addWidget(Section("Layout", layout_box))

        stats = QWidget()
        form = form_layout()
        stats.setLayout(form)
        self.error_mode = fill_combo(QComboBox(), ERROR_MODE_NAMES)
        self.error_mode.setToolTip("SD: Streuung der Einzelmessungen (Stichprobe, n−1)\n"
                                   "SEM: Unsicherheit des Mittelwerts (SD/√n)\n"
                                   "95 %-KI: Konfidenzintervall des Mittelwerts (t-Verteilung)")
        self.stat_style = fill_combo(QComboBox(), STAT_STYLES)
        form.addRow("Fehlermaß", self.error_mode)
        form.addRow("Darstellung", self.stat_style)
        layout.addWidget(Section("Statistik (Messwiederholungen)", stats))
        layout.addStretch()

        self.title.textChanged.connect(self.changed)
        for spin in (self.label_size, self.tick_size, self.legend_size):
            spin.valueChanged.connect(self.changed)
        for combo in (self.legend, self.error_mode, self.stat_style):
            combo.currentIndexChanged.connect(self.changed)
        self.grid.toggled.connect(self.changed)
        self.minor.toggled.connect(self.changed)

    @staticmethod
    def _size(value: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(4, 96)
        spin.setSuffix(" pt")
        spin.setValue(value)
        return spin

    def apply_to(self, s: PlotSettings) -> None:
        s.title = self.title.text()
        s.label_fontsize = self.label_size.value()
        s.tick_fontsize = self.tick_size.value()
        s.legend_fontsize = self.legend_size.value()
        s.legend_loc = self.legend.currentData()
        s.grid = self.grid.isChecked()
        s.minor_ticks = self.minor.isChecked()
        s.error_mode = self.error_mode.currentData()
        s.stat_style = self.stat_style.currentData()

    def load(self, s: PlotSettings) -> None:
        self.title.setText(s.title)
        self.label_size.setValue(int(s.label_fontsize))
        self.tick_size.setValue(int(s.tick_fontsize))
        self.legend_size.setValue(int(s.legend_fontsize))
        set_combo(self.legend, s.legend_loc)
        self.grid.setChecked(s.grid)
        self.minor.setChecked(s.minor_ticks)
        set_combo(self.error_mode, s.error_mode)
        set_combo(self.stat_style, s.stat_style)


class ExportPanel(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 10)

        size = QWidget()
        form = form_layout()
        size.setLayout(form)
        self.width = self._cm(16.0)
        self.height = self._cm(10.0)
        self.dpi = QSpinBox()
        self.dpi.setRange(50, 1200)
        self.dpi.setSingleStep(50)
        self.dpi.setValue(300)
        self.dpi.setSuffix(" dpi")
        self.dpi.setToolTip("Bei Vektorformaten bestimmt die Auflösung, wie fein die Datenreduktion arbeitet.")
        form.addRow("Breite", self.width)
        form.addRow("Höhe", self.height)
        form.addRow("Auflösung", self.dpi)
        layout.addWidget(Section("Größe", size))

        vector = QWidget()
        form = form_layout()
        vector.setLayout(form)
        self.reduce = QCheckBox("Datenreduktion (optisch verlustfrei)")
        self.reduce.setToolTip("Je Pixelspalte bleiben erster, kleinster, größter und letzter Punkt erhalten.\n"
                               "Spitzen und Ausreißer bleiben sichtbar; unsichtbare Punkte entfallen.")
        self.thin = QCheckBox("Marker/Fehlerbalken begrenzen")
        self.thin.setToolTip("Linie + Marker: nur jeder n-te Punkt bekommt einen Marker/Fehlerbalken.\n"
                             "Nur Marker: deckungsgleiche Marker werden zusammengefasst.")
        self.limit = QSpinBox()
        self.limit.setRange(10, 100000)
        self.limit.setSingleStep(50)
        self.limit.setSuffix(" je Datensatz")
        self.text = QCheckBox("Text bearbeitbar (echte Schrift)")
        self.text.setToolTip("Beschriftungen bleiben in Inkscape, Illustrator, PowerPoint usw. bearbeitbar.\n"
                             "Ohne Haken wird Text in Kurven umgewandelt.")
        self.raster = QCheckBox("Datenlinien rastern (Notlösung)")
        self.raster.setToolTip("Nur nötig, wenn die Datei trotz Reduktion zu groß ist.")
        form.addRow(self.reduce)
        form.addRow(self.thin)
        form.addRow("Höchstens", self.limit)
        form.addRow(self.text)
        form.addRow(self.raster)
        form.addRow(_muted("Gilt für PDF, SVG und EPS. Rasterformate (PNG usw.) verwenden nur die "
                           "Datenreduktion. Ohne Optimierung entstehen bei vielen Messpunkten "
                           "Dateien, die kaum noch zu öffnen sind."))
        layout.addWidget(Section("Vektorgrafik", vector))
        layout.addStretch()

        for spin in (self.width, self.height):
            spin.valueChanged.connect(self.changed)
        for spin in (self.dpi, self.limit):
            spin.valueChanged.connect(self.changed)
        for check in (self.reduce, self.thin, self.text, self.raster):
            check.toggled.connect(self.changed)
        self.thin.toggled.connect(self.limit.setEnabled)
        self.load(ExportSettings())

    @staticmethod
    def _cm(value: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(2, 100)
        spin.setDecimals(1)
        spin.setSingleStep(0.5)
        spin.setSuffix(" cm")
        spin.setValue(value)
        return spin

    def settings(self) -> ExportSettings:
        return ExportSettings(width_cm=self.width.value(), height_cm=self.height.value(),
                              dpi=self.dpi.value(), reduce_data=self.reduce.isChecked(),
                              thin_markers=self.thin.isChecked(), marker_limit=self.limit.value(),
                              editable_text=self.text.isChecked(), rasterize=self.raster.isChecked())

    def load(self, e: ExportSettings) -> None:
        self.width.setValue(e.width_cm)
        self.height.setValue(e.height_cm)
        self.dpi.setValue(int(e.dpi))
        self.reduce.setChecked(e.reduce_data)
        self.thin.setChecked(e.thin_markers)
        self.limit.setValue(int(e.marker_limit))
        self.limit.setEnabled(e.thin_markers)
        self.text.setChecked(e.editable_text)
        self.raster.setChecked(e.rasterize)
