"""Dialoge: Import mit Vorschau, Darstellung eines Datensatzes, Export-Optionen."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QBrush, QColor, QFont
from PyQt5.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                             QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                             QListWidget, QListWidgetItem, QMessageBox, QSpinBox, QTableWidget,
                             QTableWidgetItem, QVBoxLayout)

from ..fitting import FIT_KINDS
from ..loaders import LoadError, Table, column_names, detect_layout, load_datasets, read_table
from ..model import DRAW_MODES, LINESTYLES, MARKERS, Dataset, ImportSpec

PREVIEW_ROWS = 60


def _fill_combo(combo: QComboBox, mapping: dict, current) -> None:
    for key, text in mapping.items():
        combo.addItem(text, key)
    index = combo.findData(current)
    combo.setCurrentIndex(max(index, 0))


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

class ImportDialog(QDialog):
    """Vorschau einer Datei mit Auswahl von Tabellenblatt, Kopfzeile, X- und Y-Spalten."""

    def __init__(self, parent, path: str, table: Table, spec: ImportSpec):
        super().__init__(parent)
        self.setWindowTitle(f"Import – {Path(path).name}")
        self.resize(900, 640)
        self.path = path
        self.table = table
        self._updating = False

        layout = QVBoxLayout(self)
        options = QGroupBox("Aufbau der Datei")
        form = QFormLayout(options)

        self.sheet_combo = QComboBox()
        self.sheet_combo.addItems(table.sheets)
        if table.sheet:
            self.sheet_combo.setCurrentText(table.sheet)
        self.sheet_combo.currentTextChanged.connect(self._sheet_changed)
        if len(table.sheets) > 1:
            form.addRow("Tabellenblatt:", self.sheet_combo)

        self.header_spin = QSpinBox()
        self.header_spin.setSpecialValueText("keine")
        self.header_spin.setToolTip("Zeile mit den Spaltennamen (keine = Spalten werden durchnummeriert)")
        self.data_spin = QSpinBox()
        self.data_spin.setMinimum(1)
        self.data_spin.setToolTip("Erste Zeile mit Messwerten; Zeilen davor werden ignoriert")
        rows_layout = QHBoxLayout()
        rows_layout.addWidget(QLabel("Kopfzeile:"))
        rows_layout.addWidget(self.header_spin)
        rows_layout.addSpacing(16)
        rows_layout.addWidget(QLabel("Daten ab Zeile:"))
        rows_layout.addWidget(self.data_spin)
        rows_layout.addStretch()
        form.addRow(rows_layout)

        self.x_combo = QComboBox()
        form.addRow("X-Spalte:", self.x_combo)

        self.y_list = QListWidget()
        self.y_list.setMaximumHeight(120)
        form.addRow("Y-Spalten:", self.y_list)

        self.stat_check = QCheckBox("Y-Spalten als Messwiederholungen zusammenfassen (Mittelwert ± Fehler)")
        self.stat_check.setChecked(spec.statistics)
        self.sort_check = QCheckBox("Nach X-Werten sortieren")
        self.sort_check.setChecked(spec.sort_x)
        form.addRow(self.stat_check)
        form.addRow(self.sort_check)

        self.info_label = QLabel()
        self.info_label.setStyleSheet("color: #555;")
        self.info_label.setWordWrap(True)
        form.addRow(self.info_label)
        layout.addWidget(options)

        layout.addWidget(QLabel("Vorschau (Kopfzeile fett, ignorierte Zeilen grau):"))
        self.preview = QTableWidget()
        self.preview.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout.addWidget(self.preview, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Importieren")
        buttons.button(QDialogButtonBox.Cancel).setText("Abbrechen")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.header_spin.valueChanged.connect(self._layout_changed)
        self.data_spin.valueChanged.connect(self._layout_changed)
        self.x_combo.currentIndexChanged.connect(self._x_changed)

        self._apply_table(spec)

    # Hilfsfunktionen -------------------------------------------------------

    def _apply_table(self, spec: ImportSpec) -> None:
        """Steuerelemente für die aktuelle Tabelle und die gegebenen Einstellungen setzen."""
        self._updating = True
        n_rows = max(len(self.table.rows), 1)
        self.header_spin.setRange(0, n_rows)
        self.data_spin.setRange(1, n_rows)
        self.header_spin.setValue(spec.header_row + 1 if spec.header_row is not None else 0)
        self.data_spin.setValue(spec.data_start + 1)
        self._updating = False
        self._refresh_columns(spec.x_col, spec.y_cols)
        self._refresh_preview()

    def _current_header(self) -> Optional[int]:
        value = self.header_spin.value()
        return value - 1 if value > 0 else None

    def _refresh_columns(self, x_col: int, y_cols: list[int]) -> None:
        self._updating = True
        names = column_names(self.table, self._current_header())
        self.x_combo.clear()
        for i, name in enumerate(names):
            self.x_combo.addItem(f"{i + 1}: {name}", i)
        self.x_combo.setCurrentIndex(x_col if 0 <= x_col < len(names) else 0)
        self.y_list.clear()
        selected = set(y_cols) if y_cols else set(range(len(names)))
        for i, name in enumerate(names):
            item = QListWidgetItem(f"{i + 1}: {name}")
            item.setData(Qt.UserRole, i)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if i in selected else Qt.Unchecked)
            self.y_list.addItem(item)
        self._updating = False
        self._x_changed()

    def _checked_y(self) -> list[int]:
        result = []
        for i in range(self.y_list.count()):
            item = self.y_list.item(i)
            if item.checkState() == Qt.Checked and not item.isHidden():
                result.append(item.data(Qt.UserRole))
        return result

    def _x_changed(self) -> None:
        if self._updating:
            return
        x_col = self.x_combo.currentData()
        for i in range(self.y_list.count()):
            item = self.y_list.item(i)
            item.setHidden(item.data(Qt.UserRole) == x_col)

    def _refresh_preview(self) -> None:
        rows = self.table.rows[:PREVIEW_ROWS]
        width = self.table.width
        header = self._current_header()
        data_start = self.data_spin.value() - 1
        self.preview.clear()
        self.preview.setRowCount(len(rows))
        self.preview.setColumnCount(width)
        self.preview.setHorizontalHeaderLabels([str(i + 1) for i in range(width)])
        bold = QFont()
        bold.setBold(True)
        grey = QBrush(QColor("#9e9e9e"))
        for r, row in enumerate(rows):
            for c in range(width):
                cell = row[c] if c < len(row) else None
                item = QTableWidgetItem("" if cell is None else str(cell))
                if r == header:
                    item.setFont(bold)
                    item.setBackground(QBrush(QColor("#e3f2fd")))
                elif r < data_start:
                    item.setForeground(grey)
                self.preview.setItem(r, c, item)
        self.preview.resizeColumnsToContents()

        info = [self.table.info] if self.table.info else []
        info.append(f"{len(self.table.rows)} Zeilen, {width} Spalten")
        if len(self.table.rows) > PREVIEW_ROWS:
            info.append(f"Vorschau zeigt die ersten {PREVIEW_ROWS} Zeilen")
        self.info_label.setText(" · ".join(info))

    # Reaktionen ------------------------------------------------------------

    def _sheet_changed(self, sheet: str) -> None:
        if self._updating or not sheet:
            return
        try:
            self.table = read_table(self.path, sheet)
        except LoadError as exc:
            QMessageBox.warning(self, "Fehler", str(exc))
            return
        header_row, data_start = detect_layout(self.table.rows)
        self._apply_table(ImportSpec(path=self.path, sheet=sheet, header_row=header_row,
                                     data_start=data_start))

    def _layout_changed(self) -> None:
        if self._updating:
            return
        header = self._current_header()
        if header is not None and self.data_spin.value() - 1 <= header:
            self._updating = True
            self.data_spin.setValue(header + 2)
            self._updating = False
        self._refresh_columns(self.x_combo.currentData() or 0, self._checked_y())
        self._refresh_preview()

    def spec(self) -> ImportSpec:
        return ImportSpec(
            path=self.path,
            sheet=self.table.sheet,
            header_row=self._current_header(),
            data_start=self.data_spin.value() - 1,
            x_col=self.x_combo.currentData() or 0,
            y_cols=self._checked_y(),
            statistics=self.stat_check.isChecked(),
            sort_x=self.sort_check.isChecked(),
        )

    def _accept(self) -> None:
        spec = self.spec()
        if not spec.y_cols:
            QMessageBox.warning(self, "Import", "Bitte mindestens eine Y-Spalte auswählen.")
            return
        try:
            result = load_datasets(spec, self.table)
        except LoadError as exc:
            QMessageBox.warning(self, "Import", str(exc))
            return
        if not result.datasets:
            QMessageBox.warning(self, "Import", "Mit diesen Einstellungen werden keine gültigen Daten "
                                                "gefunden. Bitte Kopfzeile, Datenbeginn und Spalten prüfen.")
            return
        self.accept()


# ---------------------------------------------------------------------------
# Darstellung eines Datensatzes
# ---------------------------------------------------------------------------

class StyleDialog(QDialog):
    """Linien-, Marker- und Fit-Einstellungen eines Datensatzes."""

    def __init__(self, parent, dataset: Dataset):
        super().__init__(parent)
        self.setWindowTitle(f"Darstellung – {dataset.display_label}")
        self.dataset = dataset
        form = QFormLayout(self)

        self.draw_combo = QComboBox()
        _fill_combo(self.draw_combo, DRAW_MODES, dataset.draw)
        self.linestyle_combo = QComboBox()
        _fill_combo(self.linestyle_combo, LINESTYLES, dataset.linestyle)
        self.linewidth_spin = QDoubleSpinBox()
        self.linewidth_spin.setRange(0.2, 10)
        self.linewidth_spin.setSingleStep(0.5)
        self.linewidth_spin.setValue(dataset.linewidth)
        self.marker_combo = QComboBox()
        _fill_combo(self.marker_combo, MARKERS, dataset.marker)
        self.markersize_spin = QDoubleSpinBox()
        self.markersize_spin.setRange(1, 30)
        self.markersize_spin.setValue(dataset.markersize)
        self.filled_check = QCheckBox("Marker gefüllt")
        self.filled_check.setChecked(dataset.marker_filled)
        self.fit_combo = QComboBox()
        _fill_combo(self.fit_combo, FIT_KINDS, dataset.fit)
        self.fit_combo.setToolTip("Die Anpassung erfolgt in den angezeigten (skalierten) Einheiten\n"
                                  "über die sichtbaren Datenpunkte (X-Grenzen werden berücksichtigt).")
        self.all_check = QCheckBox("Linien- und Markereinstellungen auf alle Datensätze anwenden")

        form.addRow("Darstellung:", self.draw_combo)
        form.addRow("Linienstil:", self.linestyle_combo)
        form.addRow("Linienbreite:", self.linewidth_spin)
        form.addRow("Marker:", self.marker_combo)
        form.addRow("Markergröße:", self.markersize_spin)
        form.addRow(self.filled_check)
        form.addRow("Kurvenanpassung:", self.fit_combo)
        form.addRow(self.all_check)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Cancel).setText("Abbrechen")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def line_style(self) -> dict:
        return {
            "draw": self.draw_combo.currentData(),
            "linestyle": self.linestyle_combo.currentData(),
            "linewidth": self.linewidth_spin.value(),
            "marker": self.marker_combo.currentData(),
            "markersize": self.markersize_spin.value(),
            "marker_filled": self.filled_check.isChecked(),
        }

    def fit_kind(self) -> str:
        return self.fit_combo.currentData()

    def apply_to_all(self) -> bool:
        return self.all_check.isChecked()


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

class ExportDialog(QDialog):
    """Größe, Auflösung und Rasterung für den Export."""

    def __init__(self, parent, width_cm: float, height_cm: float, dpi: int,
                 use_window: bool, rasterize: bool, vector_format: bool):
        super().__init__(parent)
        self.setWindowTitle("Export-Optionen")
        form = QFormLayout(self)

        self.window_check = QCheckBox("Größe des Plot-Fensters verwenden")
        self.window_check.setChecked(use_window)
        self.width_spin = QDoubleSpinBox()
        self.width_spin.setRange(2, 100)
        self.width_spin.setSuffix(" cm")
        self.width_spin.setValue(width_cm)
        self.height_spin = QDoubleSpinBox()
        self.height_spin.setRange(2, 100)
        self.height_spin.setSuffix(" cm")
        self.height_spin.setValue(height_cm)
        self.dpi_spin = QSpinBox()
        self.dpi_spin.setRange(50, 1200)
        self.dpi_spin.setSingleStep(50)
        self.dpi_spin.setValue(dpi)
        self.dpi_spin.setToolTip("Bei Vektorformaten bestimmt die Auflösung, wie fein die Datenreduktion arbeitet.")

        self.reduce_check = QCheckBox("Datenreduktion (optisch verlustfrei)")
        self.reduce_check.setChecked(True)
        self.reduce_check.setToolTip("Je Pixelspalte bleiben erster, kleinster, größter und letzter Punkt erhalten.\n"
                                     "Spitzen und Ausreißer bleiben sichtbar; unsichtbare Punkte entfallen.")
        self.thin_check = QCheckBox("Marker und Fehlerbalken begrenzen, max. je Datensatz:")
        self.thin_check.setChecked(True)
        self.thin_check.setToolTip("Linie + Marker: nur jeder n-te Punkt bekommt einen Marker/Fehlerbalken.\n"
                                   "Nur Marker: deckungsgleiche Marker werden zusammengefasst.\n"
                                   "Hauptursache für langsame Vektorgrafiken: jeder Marker ist ein eigenes Objekt.")
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(10, 100000)
        self.limit_spin.setSingleStep(50)
        self.limit_spin.setValue(250)
        thin_row = QHBoxLayout()
        thin_row.addWidget(self.thin_check)
        thin_row.addWidget(self.limit_spin)
        thin_row.addStretch()
        self.text_check = QCheckBox("Text bearbeitbar (echte Schrift statt Pfade)")
        self.text_check.setChecked(True)
        self.text_check.setToolTip("Beschriftungen bleiben in Inkscape, Illustrator, PowerPoint usw. bearbeitbar.\n"
                                   "Ohne Haken wird Text in Kurven umgewandelt (sieht überall identisch aus).")
        self.raster_check = QCheckBox("Datenlinien zusätzlich rastern (Notlösung)")
        self.raster_check.setChecked(rasterize)
        self.raster_check.setToolTip("Achsen und Text bleiben Vektorgrafik; die Datenlinien werden als Bild\n"
                                     "eingebettet. Nur nötig, wenn die Datei trotz Reduktion zu groß ist.")
        self.thin_check.toggled.connect(self.limit_spin.setEnabled)
        for widget in (self.thin_check, self.limit_spin, self.text_check, self.raster_check):
            widget.setVisible(vector_format)

        hint = QLabel("Schriftgrößen sind in Punkt angegeben: Bei kleiner Exportgröße wirken sie größer.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #555;")

        form.addRow(self.window_check)
        form.addRow("Breite:", self.width_spin)
        form.addRow("Höhe:", self.height_spin)
        form.addRow("Auflösung:", self.dpi_spin)
        form.addRow(self.reduce_check)
        form.addRow(thin_row)
        form.addRow(self.text_check)
        form.addRow(self.raster_check)
        form.addRow(hint)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Exportieren")
        buttons.button(QDialogButtonBox.Cancel).setText("Abbrechen")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

        self.window_check.toggled.connect(self._toggle)
        self._toggle(use_window)

    def _toggle(self, use_window: bool) -> None:
        self.width_spin.setEnabled(not use_window)
        self.height_spin.setEnabled(not use_window)

    def values(self) -> dict:
        return {
            "use_window": self.window_check.isChecked(),
            "width_cm": self.width_spin.value(),
            "height_cm": self.height_spin.value(),
            "dpi": self.dpi_spin.value(),
            "reduce_data": self.reduce_check.isChecked(),
            "thin_markers": self.thin_check.isChecked(),
            "marker_limit": self.limit_spin.value(),
            "editable_text": self.text_check.isChecked(),
            "rasterize": self.raster_check.isChecked(),
        }
