"""Importdialog mit Vorschau: Tabellenblatt, Kopfzeile, Datenbeginn, X- und Y-Spalten."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                               QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMessageBox,
                               QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from ..loaders import LoadError, Table, column_names, detect_layout, load_datasets, read_table
from ..model import ImportSpec
from . import theme
from .widgets import form_layout

PREVIEW_ROWS = 60


class ImportDialog(QDialog):
    def __init__(self, parent, path: str, table: Table, spec: ImportSpec):
        super().__init__(parent)
        self.setWindowTitle(f"Import – {Path(path).name}")
        self.resize(940, 660)
        self.path = path
        self.table = table
        self._updating = False

        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        layout.addLayout(top)

        options = QWidget()
        form = form_layout()
        options.setLayout(form)
        options.setMinimumWidth(380)

        self.sheet_combo = QComboBox()
        self.sheet_combo.addItems(table.sheets)
        if table.sheet:
            self.sheet_combo.setCurrentText(table.sheet)
        self.sheet_combo.currentTextChanged.connect(self._sheet_changed)
        if len(table.sheets) > 1:
            form.addRow("Tabellenblatt", self.sheet_combo)

        self.header_spin = QSpinBox()
        self.header_spin.setSpecialValueText("keine")
        self.header_spin.setToolTip("Zeile mit den Spaltennamen (keine = Spalten werden durchnummeriert)")
        self.data_spin = QSpinBox()
        self.data_spin.setMinimum(1)
        self.data_spin.setToolTip("Erste Zeile mit Messwerten; Zeilen davor werden ignoriert")
        form.addRow("Kopfzeile", self.header_spin)
        form.addRow("Daten ab Zeile", self.data_spin)

        self.x_combo = QComboBox()
        form.addRow("X-Spalte", self.x_combo)
        self.y_list = QListWidget()
        self.y_list.setMinimumHeight(110)
        form.addRow("Y-Spalten", self.y_list)

        self.stat_check = QCheckBox("Y-Spalten als Messwiederholungen\nzusammenfassen (Mittelwert ± Fehler)")
        self.stat_check.setChecked(spec.statistics)
        self.sort_check = QCheckBox("Nach X-Werten sortieren")
        self.sort_check.setChecked(spec.sort_x)
        form.addRow("", self.stat_check)
        form.addRow("", self.sort_check)
        top.addWidget(options)

        right = QVBoxLayout()
        hint = QLabel("Vorschau – Kopfzeile hervorgehoben, ignorierte Zeilen grau")
        hint.setObjectName("Muted")
        right.addWidget(hint)
        self.preview = QTableWidget()
        self.preview.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        right.addWidget(self.preview, 1)
        self.info_label = QLabel()
        self.info_label.setObjectName("Muted")
        self.info_label.setWordWrap(True)
        right.addWidget(self.info_label)
        top.addLayout(right, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok.setText("Importieren")
        ok.setProperty("primary", True)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Abbrechen")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.header_spin.valueChanged.connect(self._layout_changed)
        self.data_spin.valueChanged.connect(self._layout_changed)
        self.x_combo.currentIndexChanged.connect(self._x_changed)
        self._apply_table(spec)

    # Hilfsfunktionen -------------------------------------------------------

    def _apply_table(self, spec: ImportSpec) -> None:
        self._updating = True
        self.header_spin.setRange(0, max(len(self.table.rows), 1))   # Kopfzeile nur in der Vorschau
        self.data_spin.setRange(1, max(self.table.n_rows, len(self.table.rows), 1))
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
            item.setData(Qt.ItemDataRole.UserRole, i)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if i in selected else Qt.CheckState.Unchecked)
            self.y_list.addItem(item)
        self._updating = False
        self._x_changed()

    def _checked_y(self) -> list[int]:
        result = []
        for i in range(self.y_list.count()):
            item = self.y_list.item(i)
            if item.checkState() == Qt.CheckState.Checked and not item.isHidden():
                result.append(item.data(Qt.ItemDataRole.UserRole))
        return result

    def _x_changed(self) -> None:
        if self._updating:
            return
        x_col = self.x_combo.currentData()
        for i in range(self.y_list.count()):
            item = self.y_list.item(i)
            item.setHidden(item.data(Qt.ItemDataRole.UserRole) == x_col)

    def _refresh_preview(self) -> None:
        c = theme.colors()
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
        for r, row in enumerate(rows):
            for col in range(width):
                cell = row[col] if col < len(row) else None
                item = QTableWidgetItem("" if cell is None else str(cell))
                if r == header:
                    item.setFont(bold)
                    item.setBackground(QBrush(QColor(c["selection"])))
                elif r < data_start:
                    item.setForeground(QBrush(QColor(c["muted"])))
                self.preview.setItem(r, col, item)
        self.preview.resizeColumnsToContents()

        info = [self.table.info] if self.table.info else []
        total = max(self.table.n_rows, len(self.table.rows))
        info.append(f"{total:,} Zeilen, {width} Spalten".replace(",", "."))
        if total > PREVIEW_ROWS:
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
