"""Wiederverwendbare Eingabe-Widgets."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QFormLayout, QHBoxLayout,
                               QLineEdit, QPushButton, QSizePolicy, QToolButton, QVBoxLayout,
                               QWidget)

from ..numparse import parse_optional
from ..plotting import SI_PREFIXES, AxisSettings


def format_number(value: Optional[float]) -> str:
    """Zahl für ein Eingabefeld formatieren (deutsches Dezimalkomma)."""
    return "" if value is None else f"{value:g}".replace(".", ",")


def form_layout() -> QFormLayout:
    form = QFormLayout()
    form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
    form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
    form.setHorizontalSpacing(10)
    form.setVerticalSpacing(7)
    form.setContentsMargins(4, 2, 4, 8)
    return form


def fill_combo(combo: QComboBox, mapping: dict, current=None) -> QComboBox:
    for key, text in mapping.items():
        combo.addItem(text, key)
    if current is not None:
        set_combo(combo, current)
    return combo


def set_combo(combo: QComboBox, value) -> None:
    index = combo.findData(value)
    if index >= 0:
        combo.setCurrentIndex(index)


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
        valid = self.is_valid()
        self.setProperty("invalid", not valid)
        self.style().unpolish(self)
        self.style().polish(self)
        hint = "" if valid else "Ungültige Zahl – erlaubt sind z. B. 0,5 · 1.5 · 2,3E-6"
        if not valid and self._positive:
            hint += " (größer als 0)"
        self.setToolTip(hint)


class ColorButton(QPushButton):
    """Farbfeld, das per Klick einen Farbdialog öffnet."""

    colorChanged = Signal(str)

    def __init__(self, color: str = "#1f77b4", parent=None):
        super().__init__(parent)
        self.setFixedSize(46, 24)
        self.setToolTip("Farbe ändern")
        self._color = color
        self.set_color(color)
        self.clicked.connect(self._choose)

    def color(self) -> str:
        return self._color

    def set_color(self, color: str) -> None:
        self._color = color
        self.setStyleSheet(f"QPushButton {{ background-color: {color}; border: 1px solid rgba(0,0,0,0.25);"
                           " border-radius: 5px; }}")

    def _choose(self) -> None:
        color = QColorDialog.getColor(QColor(self._color), self, "Farbe auswählen")
        if color.isValid():
            self.set_color(color.name())
            self.colorChanged.emit(color.name())


def prefix_combo() -> QComboBox:
    combo = QComboBox()
    for key in SI_PREFIXES:
        combo.addItem("– (keiner)" if key == "1" else key, key)
    set_combo(combo, "1")
    combo.setToolTip("Werte werden in dieser Einheit angezeigt (z. B. 0,002 V → 2 mV).\n"
                     "Grenzen und Tick-Abstände gelten in der angezeigten Einheit.")
    return combo


class Section(QWidget):
    """Einklappbarer Abschnitt mit Überschrift."""

    def __init__(self, title: str, content: QWidget, expanded: bool = True, parent=None):
        super().__init__(parent)
        self.header = QToolButton()
        self.header.setObjectName("SectionHeader")
        self.header.setText(title)
        self.header.setCheckable(True)
        self.header.setChecked(expanded)
        self.header.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.header.toggled.connect(self._toggle)
        self.content = content
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.header)
        layout.addWidget(content)
        self._toggle(expanded)

    def _toggle(self, expanded: bool) -> None:
        self.header.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)
        self.content.setVisible(expanded)


class AxisEditor(QWidget):
    """Einstellungen einer Achse: Beschriftung, Einheit, Präfix, Grenzen, Tick, Log."""

    changed = Signal()

    def __init__(self, name: str, label_hint: str, unit_hint: str, parent=None):
        super().__init__(parent)
        self.name = name
        form = form_layout()
        self.setLayout(form)

        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText(label_hint)
        self.label_edit.setToolTip("Formeln sind möglich, z. B. $\\Delta U$ oder $\\mu$")
        self.unit_edit = QLineEdit()
        self.unit_edit.setPlaceholderText(unit_hint)
        self.prefix = prefix_combo()
        unit_row = QHBoxLayout()
        unit_row.addWidget(self.unit_edit, 1)
        unit_row.addWidget(self.prefix)

        self.min_edit = NumberEdit()
        self.max_edit = NumberEdit()
        range_row = QHBoxLayout()
        range_row.addWidget(self.min_edit)
        range_row.addWidget(self.max_edit)
        self.tick_edit = NumberEdit(positive=True)
        self.log_check = QCheckBox("Logarithmisch")

        form.addRow("Beschriftung", self.label_edit)
        form.addRow("Einheit", unit_row)
        form.addRow("Min / Max", range_row)
        form.addRow("Tick-Abstand", self.tick_edit)
        form.addRow("", self.log_check)

        for edit in (self.label_edit, self.unit_edit, self.min_edit, self.max_edit, self.tick_edit):
            edit.textChanged.connect(self.changed)
        self.prefix.currentIndexChanged.connect(self.changed)
        self.log_check.toggled.connect(self.changed)

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
        set_combo(self.prefix, axis.prefix if self.prefix.findData(axis.prefix) >= 0 else "1")
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
        lo, hi = (format_number(float(f"{v:.4g}")) for v in limits)
        self.min_edit.setPlaceholderText(f"Auto ({lo})")
        self.max_edit.setPlaceholderText(f"Auto ({hi})")
