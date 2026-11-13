"""Hauptfenster des Graph Plotters."""

from __future__ import annotations

from pathlib import Path

import matplotlib
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from PyQt5.QtCore import QEvent, QItemSelectionModel, Qt
from PyQt5.QtGui import QFont, QKeySequence
from PyQt5.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog,
                             QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel,
                             QLineEdit, QMainWindow, QMessageBox, QPushButton, QScrollArea,
                             QShortcut, QSpinBox, QTableWidget, QToolButton, QVBoxLayout, QWidget)

from .. import VERSION
from ..exporting import FORMATS, ExportOptions, export_plot, is_vector, normalize_extension
from ..loaders import (CSV_EXTENSIONS, EXCEL_EXTENSIONS, LoadError, default_spec, is_supported,
                       load_datasets, read_table)
from ..model import DEFAULT_COLORS, Dataset
from ..plotting import LEGEND_LOCATIONS, STAT_STYLES, PlotError, PlotSettings, render
from ..project import PROJECT_EXTENSION, load_project, save_project
from ..stats import ERROR_MODE_NAMES
from .dialogs import ExportDialog, ImportDialog, StyleDialog
from .widgets import AxisBox, ColorButton

# (Filtertext, Endung) für den Speichern-Dialog
EXPORT_FILTERS = [(f"{text} (*.{ext})", ext) for ext, (text, _) in FORMATS.items()]

COL_VISIBLE, COL_COLOR, COL_LABEL, COL_AXIS, COL_STYLE = range(5)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Graph Plotter (v{VERSION})")
        self.resize(1400, 850)
        self.setAcceptDrops(True)

        self.datasets: list[Dataset] = []
        self._has_plot = False
        self._last_dir = str(Path.home())
        self._export = {"use_window": True, "width_cm": 16.0, "height_cm": 10.0, "dpi": 300}

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.addWidget(self._build_control_panel())

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        self.fig = Figure(figsize=(8, 6), dpi=100)
        self.canvas = FigureCanvas(self.fig)
        self.toolbar = NavigationToolbar(self.canvas, self)
        right_layout.addWidget(self.toolbar)
        right_layout.addWidget(self.canvas, 1)
        layout.addWidget(right, 1)
        self.setCentralWidget(central)

        self.statusBar().showMessage("Dateien laden: Button „Dateien laden…“ oder per Drag & Drop ins Fenster.")
        self._apply_y2_visibility()

    # ------------------------------------------------------------------ Aufbau

    def _build_control_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        layout.addWidget(self._build_data_box())

        stat_box = QGroupBox("Statistik (Messwiederholungen)")
        stat_form = QFormLayout(stat_box)
        self.error_mode_combo = QComboBox()
        for key, text in ERROR_MODE_NAMES.items():
            self.error_mode_combo.addItem(text, key)
        self.error_mode_combo.setToolTip("SD: Streuung der Einzelmessungen (Stichprobe, n−1)\n"
                                         "SEM: Unsicherheit des Mittelwerts (SD/√n)\n"
                                         "95 %-KI: Konfidenzintervall des Mittelwerts (t-Verteilung)")
        self.stat_style_combo = QComboBox()
        for key, text in STAT_STYLES.items():
            self.stat_style_combo.addItem(text, key)
        stat_form.addRow("Fehlermaß:", self.error_mode_combo)
        stat_form.addRow("Darstellung:", self.stat_style_combo)
        layout.addWidget(stat_box)

        self.x_box = AxisBox("X-Achse", "X-Achse", "Zeit", "z. B. s")
        self.y_box = AxisBox("Y-Achse", "Y-Achse", "Wert", "z. B. V, m/s²")
        layout.addWidget(self.x_box)
        layout.addWidget(self.y_box)

        self.y2_check = QCheckBox("Sekundäre Y-Achse (Y2) aktivieren")
        self.y2_check.setToolTip("Datensätze werden in der Tabelle oben über die Spalte „Achse“ zugeordnet.")
        self.y2_check.toggled.connect(self._apply_y2_visibility)
        layout.addWidget(self.y2_check)
        self.y2_box = AxisBox("Y2-Achse", "Y2-Achse", "Wert 2", "z. B. °C")
        layout.addWidget(self.y2_box)
        self.y2_warning = QLabel("Hinweis: Bei aktivierter Y2-Achse die Kurvenbearbeitung über die "
                                 "Toolbar meiden – sie baut die Legende ohne Y2-Einträge neu auf.")
        self.y2_warning.setWordWrap(True)
        self.y2_warning.setStyleSheet("color: #cc7700; font-size: 9pt;")
        layout.addWidget(self.y2_warning)

        layout.addWidget(self._build_appearance_box())

        plot_button = QPushButton("Plot erstellen")
        plot_button.setFont(QFont("Arial", 12, QFont.Bold))
        plot_button.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px;")
        plot_button.setShortcut("Ctrl+R")
        plot_button.setToolTip("Strg+R")
        plot_button.clicked.connect(lambda: self.plot())
        layout.addWidget(plot_button)

        export_button = QPushButton("Plot exportieren")
        export_button.setFont(QFont("Arial", 12, QFont.Bold))
        export_button.setStyleSheet("background-color: #2196F3; color: white; padding: 10px;")
        export_button.setShortcut("Ctrl+E")
        export_button.setToolTip("Strg+E")
        export_button.clicked.connect(self.export_plot)
        layout.addWidget(export_button)
        layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidget(panel)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(450)
        scroll.setMaximumWidth(520)
        return scroll

    def _build_data_box(self) -> QGroupBox:
        box = QGroupBox("Daten")
        layout = QVBoxLayout(box)

        buttons = QHBoxLayout()
        load_button = QPushButton("Dateien laden…")
        load_button.setToolTip("CSV-, Text- und Excel-Dateien (Strg+O)")
        load_button.setShortcut("Ctrl+O")
        load_button.clicked.connect(self.choose_files)
        open_project = QPushButton("Projekt öffnen…")
        open_project.clicked.connect(self.open_project)
        save_project_button = QPushButton("Projekt speichern…")
        save_project_button.setShortcut("Ctrl+S")
        save_project_button.setToolTip("Dateien und alle Einstellungen speichern (Strg+S)")
        save_project_button.clicked.connect(self.save_project)
        for b in (load_button, open_project, save_project_button):
            buttons.addWidget(b)
        layout.addLayout(buttons)

        self.import_dialog_check = QCheckBox("Importdialog mit Vorschau anzeigen")
        self.import_dialog_check.setChecked(True)
        self.import_dialog_check.setToolTip("Ohne Dialog werden Kopfzeile und Datenbeginn automatisch erkannt;\n"
                                            "Spalte 1 = X, alle weiteren Spalten = Y.")
        self.stat_default_check = QCheckBox("Statistik-Modus: Y-Spalten als Messwiederholungen")
        self.stat_default_check.setToolTip("Voreinstellung für neu geladene Dateien: alle Y-Spalten einer Datei\n"
                                           "werden zu Mittelwert ± Fehlermaß zusammengefasst.")
        layout.addWidget(self.import_dialog_check)
        layout.addWidget(self.stat_default_check)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["", "Farbe", "Legende", "Achse", ""])
        self.table.horizontalHeaderItem(COL_VISIBLE).setToolTip("Sichtbar")
        self.table.horizontalHeaderItem(COL_STYLE).setToolTip("Darstellung und Kurvenanpassung")
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(COL_LABEL, QHeaderView.Stretch)
        for col, width in ((COL_VISIBLE, 28), (COL_COLOR, 44), (COL_AXIS, 58), (COL_STYLE, 34)):
            header.setSectionResizeMode(col, QHeaderView.Fixed)
            self.table.setColumnWidth(col, width)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setMinimumHeight(170)
        self.table.verticalHeader().setToolTip("Klicken zum Auswählen (Strg/Umschalt für Mehrfachauswahl)")
        QShortcut(QKeySequence.Delete, self.table, self.remove_selected, context=Qt.WidgetShortcut)
        layout.addWidget(self.table)

        row_buttons = QHBoxLayout()
        up = QPushButton("▲")
        up.setToolTip("Nach oben")
        up.clicked.connect(lambda: self.move_selected(-1))
        down = QPushButton("▼")
        down.setToolTip("Nach unten")
        down.clicked.connect(lambda: self.move_selected(1))
        remove = QPushButton("Entfernen")
        remove.setToolTip("Ausgewählte Datensätze entfernen (Entf)")
        remove.clicked.connect(self.remove_selected)
        remove_all = QPushButton("Alle entfernen")
        remove_all.clicked.connect(self.remove_all)
        for b in (up, down):
            b.setMaximumWidth(36)
            row_buttons.addWidget(b)
        row_buttons.addWidget(remove)
        row_buttons.addWidget(remove_all)
        layout.addLayout(row_buttons)
        return box

    def _build_appearance_box(self) -> QGroupBox:
        box = QGroupBox("Darstellung")
        form = QFormLayout(box)
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("optional")
        form.addRow("Titel:", self.title_edit)

        self.label_size = self._size_spin(30)
        self.tick_size = self._size_spin(24)
        self.legend_size = self._size_spin(30)
        sizes = QHBoxLayout()
        for text, spin in (("Achsen", self.label_size), ("Ticks", self.tick_size), ("Legende", self.legend_size)):
            sizes.addWidget(QLabel(text))
            sizes.addWidget(spin)
        form.addRow("Schrift (pt):", sizes)

        self.legend_combo = QComboBox()
        for key, text in LEGEND_LOCATIONS.items():
            self.legend_combo.addItem(text, key)
        form.addRow("Legende:", self.legend_combo)

        self.grid_check = QCheckBox("Raster")
        self.grid_check.setChecked(True)
        self.minor_check = QCheckBox("Nebenticks")
        checks = QHBoxLayout()
        checks.addWidget(self.grid_check)
        checks.addWidget(self.minor_check)
        checks.addStretch()
        form.addRow(checks)
        return box

    @staticmethod
    def _size_spin(value: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(4, 96)
        spin.setValue(value)
        return spin

    # ------------------------------------------------------------------ Datensatz-Tabelle

    def rebuild_table(self, select: list[int] | None = None) -> None:
        self.table.setRowCount(0)
        self.table.setRowCount(len(self.datasets))
        self.table.setVerticalHeaderLabels([f"G{i + 1}" for i in range(len(self.datasets))])
        y2 = self.y2_check.isChecked()

        for row, ds in enumerate(self.datasets):
            visible = QCheckBox()
            visible.setChecked(ds.visible)
            visible.setToolTip("Sichtbar")
            visible.toggled.connect(lambda checked, d=ds: setattr(d, "visible", checked))
            holder = QWidget()
            holder_layout = QHBoxLayout(holder)
            holder_layout.setContentsMargins(0, 0, 0, 0)
            holder_layout.setAlignment(Qt.AlignCenter)
            holder_layout.addWidget(visible)
            self.table.setCellWidget(row, COL_VISIBLE, holder)

            color = ColorButton(ds.color or DEFAULT_COLORS[row % len(DEFAULT_COLORS)])
            color.colorChanged.connect(lambda c, d=ds: setattr(d, "color", c))
            color_holder = QWidget()
            color_layout = QHBoxLayout(color_holder)
            color_layout.setContentsMargins(0, 0, 0, 0)
            color_layout.setAlignment(Qt.AlignCenter)
            color_layout.addWidget(color)
            self.table.setCellWidget(row, COL_COLOR, color_holder)

            label = QLineEdit(ds.label)
            label.setPlaceholderText(ds.name)
            label.setToolTip(self._dataset_tooltip(ds))
            label.textChanged.connect(lambda text, d=ds: setattr(d, "label", text))
            self._track_row(label, row)
            self.table.setCellWidget(row, COL_LABEL, label)

            axis = QComboBox()
            axis.addItems(["Y1", "Y2"])
            axis.setCurrentText(ds.axis)
            axis.setEnabled(y2)
            axis.currentTextChanged.connect(lambda text, d=ds: setattr(d, "axis", text))
            self._track_row(axis, row)
            self.table.setCellWidget(row, COL_AXIS, axis)

            style = QToolButton()
            style.setText("…")
            style.setToolTip("Darstellung und Kurvenanpassung")
            style.clicked.connect(lambda _=False, r=row: self.edit_style(r))
            self.table.setCellWidget(row, COL_STYLE, style)

        if select:
            model = self.table.selectionModel()
            for row in select:
                if 0 <= row < len(self.datasets):
                    model.select(self.table.model().index(row, 0),
                                 QItemSelectionModel.Select | QItemSelectionModel.Rows)

    @staticmethod
    def _dataset_tooltip(ds: Dataset) -> str:
        lines = []
        if ds.spec is not None:
            lines.append(ds.spec.path)
            if ds.spec.sheet:
                lines.append(f"Tabellenblatt: {ds.spec.sheet}")
        lines.append(f"{ds.n_points} Punkte")
        if ds.is_statistics:
            lines.append(f"Statistik über {ds.n_repeats} Messwiederholungen")
        return "\n".join(lines)

    def _track_row(self, widget: QWidget, row: int) -> None:
        widget.setProperty("row", row)
        widget.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.FocusIn and obj.property("row") is not None:
            self.table.selectRow(int(obj.property("row")))
        return super().eventFilter(obj, event)

    def _selected_rows(self) -> list[int]:
        return sorted({index.row() for index in self.table.selectionModel().selectedRows()})

    def move_selected(self, step: int) -> None:
        rows = self._selected_rows()
        if not rows:
            return
        if (step < 0 and rows[0] == 0) or (step > 0 and rows[-1] == len(self.datasets) - 1):
            return
        for row in (rows if step < 0 else reversed(rows)):
            self.datasets[row], self.datasets[row + step] = self.datasets[row + step], self.datasets[row]
        self.rebuild_table([r + step for r in rows])

    def remove_selected(self) -> None:
        rows = self._selected_rows()
        if not rows:
            QMessageBox.information(self, "Entfernen", "Bitte zuerst Datensätze auswählen "
                                                      "(auf die Nummer G1, G2, … links klicken).")
            return
        for row in reversed(rows):
            del self.datasets[row]
        self.rebuild_table()

    def remove_all(self) -> None:
        if not self.datasets:
            return
        if QMessageBox.question(self, "Alle entfernen", "Alle Datensätze entfernen?") != QMessageBox.Yes:
            return
        self.datasets.clear()
        self.rebuild_table()
        self.fig.clear()
        self.canvas.draw()
        self._has_plot = False

    def edit_style(self, row: int) -> None:
        ds = self.datasets[row]
        dialog = StyleDialog(self, ds)
        if dialog.exec_() != QDialog.Accepted:
            return
        style = dialog.line_style()
        targets = self.datasets if dialog.apply_to_all() else [ds]
        for target in targets:
            target.apply_style(style)
        ds.fit = dialog.fit_kind()
        if self._has_plot:
            self.plot(silent=True)

    def _apply_y2_visibility(self) -> None:
        enabled = self.y2_check.isChecked()
        self.y2_box.setVisible(enabled)
        self.y2_warning.setVisible(enabled)
        for row in range(self.table.rowCount()):
            widget = self.table.cellWidget(row, COL_AXIS)
            if widget is not None:
                widget.setEnabled(enabled)

    # ------------------------------------------------------------------ Laden

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        self.dragEnterEvent(event)

    def dropEvent(self, event):
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.toLocalFile()]
        event.acceptProposedAction()
        self.open_paths(paths)

    def open_paths(self, paths: list[str]) -> None:
        """Dateien öffnen: Projektdateien werden geöffnet, Datendateien hinzugefügt."""
        projects = [p for p in paths if p.lower().endswith(PROJECT_EXTENSION)]
        data_files = [p for p in paths if not p.lower().endswith(PROJECT_EXTENSION)]
        if projects:
            self.open_project(projects[0])
        if data_files:
            self.add_files(data_files)

    def choose_files(self) -> None:
        patterns = " ".join(f"*{ext}" for ext in CSV_EXTENSIONS + EXCEL_EXTENSIONS)
        filters = (f"Messdaten ({patterns});;"
                   f"CSV/Text ({' '.join('*' + e for e in CSV_EXTENSIONS)});;"
                   f"Excel ({' '.join('*' + e for e in EXCEL_EXTENSIONS)});;"
                   "Alle Dateien (*)")
        paths, _ = QFileDialog.getOpenFileNames(self, "Dateien laden", self._last_dir, filters)
        if paths:
            self._last_dir = str(Path(paths[0]).parent)
            self.add_files(paths)

    def _next_color(self) -> str:
        used = {d.color for d in self.datasets}
        for color in DEFAULT_COLORS:
            if color not in used:
                return color
        return DEFAULT_COLORS[len(self.datasets) % len(DEFAULT_COLORS)]

    def add_files(self, paths: list[str]) -> None:
        errors: list[str] = []
        notes: list[str] = []
        added = 0
        for path in paths:
            name = Path(path).name
            if not is_supported(path):
                errors.append(f"{name}: Dateityp wird nicht unterstützt.")
                continue
            try:
                table = read_table(path)
                spec = default_spec(path, table, statistics=self.stat_default_check.isChecked())
                if self.import_dialog_check.isChecked():
                    dialog = ImportDialog(self, path, table, spec)
                    if dialog.exec_() != QDialog.Accepted:
                        continue
                    spec, table = dialog.spec(), dialog.table
                result = load_datasets(spec, table)
            except LoadError as exc:
                errors.append(f"{name}: {exc}")
                continue

            if not result.datasets:
                errors.append(f"{name}: keine gültigen Zahlendaten gefunden.")
                continue
            for ds in result.datasets:
                ds.color = self._next_color()
                self.datasets.append(ds)
                added += 1
            if result.skipped_rows:
                notes.append(f"{name}: {result.skipped_rows} Zeile(n) mit ungültigem X-Wert übersprungen.")
            if result.empty_columns:
                notes.append(f"{name}: Spalten ohne gültige Werte ignoriert: {', '.join(result.empty_columns)}.")
            if result.x_is_time:
                notes.append(f"{name}: X-Werte sind Datum/Uhrzeit – dargestellt als Sekunden ab dem ersten Wert.")

        if added:
            self.rebuild_table()
            self.plot(silent=True)
        if errors or notes:
            text = "\n".join(errors + ([""] if errors and notes else []) + notes)
            if errors:
                QMessageBox.warning(self, "Laden", text)
            else:
                QMessageBox.information(self, "Laden", text)

    # ------------------------------------------------------------------ Einstellungen

    def collect_settings(self) -> PlotSettings:
        """Einstellungen aus der Oberfläche lesen. Raises ValueError mit allen ungültigen Feldern."""
        errors = []
        axes = {}
        for key, box in (("x", self.x_box), ("y", self.y_box), ("y2", self.y2_box)):
            try:
                axes[key] = box.settings()
            except ValueError as exc:
                if key != "y2" or self.y2_check.isChecked():
                    errors.append(str(exc))
                axes[key] = None
        if errors:
            raise ValueError("\n".join(errors))
        settings = PlotSettings(
            y2_enabled=self.y2_check.isChecked(),
            title=self.title_edit.text(),
            label_fontsize=self.label_size.value(),
            tick_fontsize=self.tick_size.value(),
            legend_fontsize=self.legend_size.value(),
            legend_loc=self.legend_combo.currentData(),
            grid=self.grid_check.isChecked(),
            minor_ticks=self.minor_check.isChecked(),
            error_mode=self.error_mode_combo.currentData(),
            stat_style=self.stat_style_combo.currentData(),
        )
        settings.x, settings.y = axes["x"], axes["y"]
        if axes["y2"] is not None:
            settings.y2 = axes["y2"]
        return settings

    def apply_settings(self, s: PlotSettings) -> None:
        self.x_box.set_settings(s.x)
        self.y_box.set_settings(s.y)
        self.y2_box.set_settings(s.y2)
        self.y2_check.setChecked(s.y2_enabled)
        self.title_edit.setText(s.title)
        self.label_size.setValue(int(s.label_fontsize))
        self.tick_size.setValue(int(s.tick_fontsize))
        self.legend_size.setValue(int(s.legend_fontsize))
        for combo, value in ((self.legend_combo, s.legend_loc), (self.error_mode_combo, s.error_mode),
                             (self.stat_style_combo, s.stat_style)):
            index = combo.findData(value)
            if index >= 0:
                combo.setCurrentIndex(index)
        self.grid_check.setChecked(s.grid)
        self.minor_check.setChecked(s.minor_ticks)

    # ------------------------------------------------------------------ Plotten

    def plot(self, silent: bool = False) -> bool:
        """Plot neu zeichnen. Mit ``silent`` werden keine Dialoge angezeigt."""
        if not self.datasets:
            if not silent:
                QMessageBox.warning(self, "Plot", "Bitte zuerst Dateien laden.")
            return False
        try:
            settings = self.collect_settings()
        except ValueError as exc:
            if not silent:
                QMessageBox.warning(self, "Ungültige Eingaben", f"Bitte diese Felder korrigieren:\n\n{exc}")
            self.statusBar().showMessage("Ungültige Eingaben – rot markierte Felder korrigieren.")
            return False

        # Für die Legende, die die Matplotlib-Toolbar bei Bearbeitung neu erzeugt
        matplotlib.rcParams["legend.fontsize"] = settings.legend_fontsize
        try:
            result = render(self.fig, self.datasets, settings)
        except PlotError as exc:
            self.fig.clear()
            self.canvas.draw()
            self._has_plot = False
            if not silent:
                QMessageBox.warning(self, "Plot", str(exc))
            self.statusBar().showMessage(str(exc).splitlines()[0])
            return False

        self.canvas.draw()
        self.toolbar.update()  # Zoom-Verlauf zurücksetzen
        self._has_plot = True
        self.x_box.set_auto(result.limits.get("x"))
        self.y_box.set_auto(result.limits.get("y"))
        self.y2_box.set_auto(result.limits.get("y2"))

        visible = [d for d in self.datasets if d.visible]
        points = sum(d.n_points for d in visible)
        message = f"{len(visible)} von {len(self.datasets)} Datensätzen dargestellt, {points} Punkte."
        if result.warnings:
            message += f" {len(result.warnings)} Hinweis(e)."
            if not silent:
                QMessageBox.information(self, "Hinweise zum Plot", "\n".join(result.warnings))
        self.statusBar().showMessage(message)
        return True

    # ------------------------------------------------------------------ Export

    def export_plot(self) -> None:
        if not self._has_plot:
            QMessageBox.warning(self, "Export", "Bitte zuerst einen Plot erstellen.")
            return
        try:
            settings = self.collect_settings()
        except ValueError as exc:
            QMessageBox.warning(self, "Ungültige Eingaben", f"Bitte diese Felder korrigieren:\n\n{exc}")
            return

        filters = ";;".join(f for f, _ in EXPORT_FILTERS)
        path, chosen = QFileDialog.getSaveFileName(self, "Plot exportieren", self._last_dir, filters)
        if not path:
            return
        ext = normalize_extension(path)
        if ext not in FORMATS:
            ext = next((e for f, e in EXPORT_FILTERS if f == chosen), "png")
            path += f".{ext}"
        self._last_dir = str(Path(path).parent)

        width_cm = self.fig.get_figwidth() * 2.54
        height_cm = self.fig.get_figheight() * 2.54
        dialog = ExportDialog(
            self,
            width_cm=self._export["width_cm"] if not self._export["use_window"] else round(width_cm, 1),
            height_cm=self._export["height_cm"] if not self._export["use_window"] else round(height_cm, 1),
            dpi=self._export["dpi"],
            use_window=self._export["use_window"],
            rasterize=False,
            vector_format=is_vector(ext),
        )
        if dialog.exec_() != QDialog.Accepted:
            return
        values = dialog.values()
        self._export.update({k: values[k] for k in ("use_window", "width_cm", "height_cm", "dpi")})

        if values["use_window"]:
            size = (self.fig.get_figwidth(), self.fig.get_figheight())
        else:
            size = (values["width_cm"] / 2.54, values["height_cm"] / 2.54)
        options = ExportOptions(width_in=size[0], height_in=size[1], dpi=values["dpi"],
                                reduce_data=values["reduce_data"], thin_markers=values["thin_markers"],
                                marker_limit=values["marker_limit"], editable_text=values["editable_text"],
                                rasterize=values["rasterize"])
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            result = export_plot(path, self.datasets, settings, options)
        except (PlotError, OSError, ValueError) as exc:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "Fehler beim Export", str(exc))
            return
        QApplication.restoreOverrideCursor()

        size_kb = Path(path).stat().st_size / 1024
        size_text = f"{size_kb / 1024:.1f} MB" if size_kb > 1024 else f"{size_kb:.0f} KB"
        message = f"Plot exportiert ({size_text}):\n{path}"
        if result.reductions:
            message += "\n\nDatenreduktion:\n" + "\n".join(result.reductions)
        QMessageBox.information(self, "Export", message)

    # ------------------------------------------------------------------ Projekt

    def save_project(self) -> None:
        if not self.datasets:
            QMessageBox.information(self, "Projekt speichern", "Es sind keine Datensätze geladen.")
            return
        try:
            settings = self.collect_settings()
        except ValueError as exc:
            QMessageBox.warning(self, "Ungültige Eingaben", f"Bitte diese Felder korrigieren:\n\n{exc}")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Projekt speichern", self._last_dir,
                                              f"Graph-Plotter-Projekt (*{PROJECT_EXTENSION})")
        if not path:
            return
        if not path.lower().endswith(PROJECT_EXTENSION):
            path += PROJECT_EXTENSION
        try:
            save_project(path, self.datasets, settings)
        except OSError as exc:
            QMessageBox.critical(self, "Projekt speichern", f"Speichern fehlgeschlagen: {exc}")
            return
        self._last_dir = str(Path(path).parent)
        self.statusBar().showMessage(f"Projekt gespeichert: {path}")

    def open_project(self, path: str | None = None) -> None:
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "Projekt öffnen", self._last_dir,
                                                  f"Graph-Plotter-Projekt (*{PROJECT_EXTENSION})")
            if not path:
                return
        if self.datasets and QMessageBox.question(
                self, "Projekt öffnen",
                "Die aktuell geladenen Datensätze werden ersetzt. Fortfahren?") != QMessageBox.Yes:
            return
        try:
            project = load_project(path)
        except LoadError as exc:
            QMessageBox.critical(self, "Projekt öffnen", str(exc))
            return
        self._last_dir = str(Path(path).parent)
        self.datasets = project.datasets
        self.apply_settings(project.settings)
        self.rebuild_table()
        self.plot(silent=True)
        self.setWindowTitle(f"Graph Plotter (v{VERSION}) – {Path(path).name}")
        if project.problems:
            QMessageBox.warning(self, "Projekt öffnen", "Nicht alles konnte geladen werden:\n\n"
                                + "\n".join(project.problems))
