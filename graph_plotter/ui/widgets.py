"""Wiederverwendbare Eingabe-Widgets."""

from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QGridLayout, QGroupBox, QLabel,
                             QLineEdit, QPushButton)

from ..numparse import parse_optional
from ..plotting import SI_PREFIXES, AxisSettings

_INVALID_STYLE = "QLineEdit { border: 2px solid #d32f2f; background: #ffebee; }"


def format_number(value: Optional[float]) -> str:
    """Zahl für ein Eingabefeld formatieren (deutsches Dezimalkomma)."""
    return "" if value is None else f"{value:g}".replace(".", ",")


class NumberEdit(QLineEdit):
    """Eingabefeld für eine optionale Zahl; ungültige Eingaben werden rot markiert."""

    def __init__(self, positive: bool = False, parent=None):
        super().__init__(parent)
        self._positive = positive
        self.setPlaceholderText("Auto")
        self.textChanged.connect(self._validate)

    def value(self) -> Optional[float]:
        """Wert oder None (leer). Raises ValueError bei ungültiger Eingabe."""
        result = parse_optional(self.text())
        if result is not None and self._positive and result <= 0:
            raise ValueError("Wert muss größer als 0 sein")
        return result

    def is_valid(self) -> bool:
        try:
            self.value()
            return True
        except ValueError:
            return False

    def set_value(self, value: Optional[float]) -> None:
        self.setText(format_number(value))

    def _validate(self) -> None:
        if self.is_valid():
            self.setStyleSheet("")
            self.setToolTip("")
        else:
            self.setStyleSheet(_INVALID_STYLE)
            hint = "Ungültige Zahl – erlaubt sind z. B. 0,5 · 1.5 · 2,3E-6"
            if self._positive:
                hint += " (größer als 0)"
            self.setToolTip(hint)


class ColorButton(QPushButton):
    """Farbfeld, das per Klick einen Farbdialog öffnet."""

    colorChanged = pyqtSignal(str)

    def __init__(self, color: str, parent=None):
        super().__init__(parent)
        self.setFixedSize(28, 22)
        self.setToolTip("Farbe ändern")
        self._color = color
        self.set_color(color)
        self.clicked.connect(self._choose)

    def set_color(self, color: str) -> None:
        self._color = color
        self.setStyleSheet(f"background-color: {color}; border: 1px solid #555; border-radius: 3px;")

    def _choose(self) -> None:
        color = QColorDialog.getColor(QColor(self._color), self, "Farbe auswählen")
        if color.isValid():
            self.set_color(color.name())
            self.colorChanged.emit(color.name())


def prefix_combo() -> QComboBox:
    combo = QComboBox()
    for key in SI_PREFIXES:
        combo.addItem("1 (keine)" if key == "1" else key, key)
    combo.setCurrentIndex(combo.findData("1"))
    combo.setToolTip("Werte werden in dieser Einheit angezeigt (z. B. 0,002 V → 2 mV).\n"
                     "Grenzen und Tick-Abstände gelten in der angezeigten Einheit.")
    return combo


class AxisBox(QGroupBox):
    """Einstellungen einer Achse: Beschriftung, Einheit, Präfix, Grenzen, Tick, Log."""

    def __init__(self, title: str, name: str, label_hint: str, unit_hint: str, parent=None):
        super().__init__(title, parent)
        self.name = name
        grid = QGridLayout(self)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)

        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText(label_hint)
        self.label_edit.setToolTip("Matplotlib-Formeln sind möglich, z. B. $\\Delta U$")
        self.unit_edit = QLineEdit()
        self.unit_edit.setPlaceholderText(unit_hint)
        self.prefix = prefix_combo()
        self.min_edit = NumberEdit()
        self.max_edit = NumberEdit()
        self.tick_edit = NumberEdit(positive=True)
        self.log_check = QCheckBox("Logarithmisch")

        grid.addWidget(QLabel("Beschriftung:"), 0, 0)
        grid.addWidget(self.label_edit, 0, 1, 1, 3)
        grid.addWidget(QLabel("Einheit:"), 1, 0)
        grid.addWidget(self.unit_edit, 1, 1)
        grid.addWidget(QLabel("Präfix:"), 1, 2)
        grid.addWidget(self.prefix, 1, 3)
        grid.addWidget(QLabel("Min:"), 2, 0)
        grid.addWidget(self.min_edit, 2, 1)
        grid.addWidget(QLabel("Max:"), 2, 2)
        grid.addWidget(self.max_edit, 2, 3)
        grid.addWidget(QLabel("Tick-Abstand:"), 3, 0)
        grid.addWidget(self.tick_edit, 3, 1)
        grid.addWidget(self.log_check, 3, 2, 1, 2)

    def settings(self) -> AxisSettings:
        """Aktuelle Einstellungen. Raises ValueError mit allen ungültigen Feldern."""
        errors = []
        values = {}
        for field_name, title, edit in (("min", "Min", self.min_edit), ("max", "Max", self.max_edit),
                                        ("tick", "Tick-Abstand", self.tick_edit)):
            try:
                values[field_name] = edit.value()
            except ValueError as exc:
                errors.append(f"{self.name} – {title}: „{edit.text()}“ ({exc})")
        if errors:
            raise ValueError("\n".join(errors))
        return AxisSettings(label=self.label_edit.text(), unit=self.unit_edit.text(),
                            prefix=self.prefix.currentData(), log=self.log_check.isChecked(), **values)

    def set_settings(self, axis: AxisSettings) -> None:
        self.label_edit.setText(axis.label)
        self.unit_edit.setText(axis.unit)
        index = self.prefix.findData(axis.prefix)
        self.prefix.setCurrentIndex(index if index >= 0 else self.prefix.findData("1"))
        self.min_edit.set_value(axis.min)
        self.max_edit.set_value(axis.max)
        self.tick_edit.set_value(axis.tick)
        self.log_check.setChecked(axis.log)

    def set_auto(self, limits: Optional[tuple]) -> None:
        """Platzhalter mit den tatsächlich verwendeten Grenzen füllen."""
        if limits is None:
            self.min_edit.setPlaceholderText("Auto")
            self.max_edit.setPlaceholderText("Auto")
            return
        self.min_edit.setPlaceholderText(f"Auto ({format_number(float(f'{limits[0]:.4g}'))})")
        self.max_edit.setPlaceholderText(f"Auto ({format_number(float(f'{limits[1]:.4g}'))})")
