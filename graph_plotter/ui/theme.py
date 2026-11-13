"""Helles und dunkles Farbschema (Fusion-Stil mit eigener Palette und Stylesheet)."""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication

THEME_MODES = {"system": "Wie Windows", "light": "Hell", "dark": "Dunkel"}

LIGHT = {
    "window": "#f4f5f7", "panel": "#ffffff", "base": "#ffffff", "alt": "#f6f7f9",
    "text": "#1f2328", "muted": "#6b7280", "border": "#d9dce1", "accent": "#2563eb",
    "accent_text": "#ffffff", "hover": "#eaeef5", "selection": "#dbe7fd", "canvas_bg": "#e6e8ec",
    "error": "#d32f2f", "error_bg": "#fdecea", "warning": "#b45309",
}
DARK = {
    "window": "#1c1d20", "panel": "#242529", "base": "#2b2c31", "alt": "#27282c",
    "text": "#e7e8ea", "muted": "#9aa0a8", "border": "#3a3c42", "accent": "#5b8ff9",
    "accent_text": "#ffffff", "hover": "#32343a", "selection": "#2e3c5a", "canvas_bg": "#141518",
    "error": "#f87171", "error_bg": "#3b1f22", "warning": "#fbbf24",
}

_current: dict = dict(LIGHT)


def colors() -> dict:
    """Aktuelle Farben (für Widgets, die selbst zeichnen)."""
    return _current


def is_dark(mode: str) -> bool:
    if mode == "dark":
        return True
    if mode == "light":
        return False
    hints = QGuiApplication.styleHints()
    return hints.colorScheme() == Qt.ColorScheme.Dark


def _indicator_files(c: dict) -> dict:
    """Kleine SVG-Grafiken für Checkboxen und Pfeile (Stylesheets brauchen Dateien)."""
    folder = Path(tempfile.gettempdir()) / "graph_plotter_theme"
    folder.mkdir(exist_ok=True)
    svgs = {
        "unchecked": f'<rect x="1.5" y="1.5" width="13" height="13" rx="3" fill="{c["base"]}" '
                     f'stroke="{c["muted"]}" stroke-width="1.2"/>',
        "checked": f'<rect x="1" y="1" width="14" height="14" rx="3" fill="{c["accent"]}"/>'
                   f'<path d="M4.5 8.2l2.4 2.4 4.6-5" fill="none" stroke="{c["accent_text"]}" '
                   'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
        "disabled": f'<rect x="1.5" y="1.5" width="13" height="13" rx="3" fill="{c["alt"]}" '
                    f'stroke="{c["border"]}" stroke-width="1.2"/>',
        "up": f'<path d="M4 10l4-4 4 4" fill="none" stroke="{c["text"]}" stroke-width="1.6" '
              'stroke-linecap="round" stroke-linejoin="round"/>',
        "down": f'<path d="M4 6l4 4 4-4" fill="none" stroke="{c["text"]}" stroke-width="1.6" '
                'stroke-linecap="round" stroke-linejoin="round"/>',
    }
    paths = {}
    for name, body in svgs.items():
        content = f'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">{body}</svg>'
        digest = hashlib.md5(content.encode()).hexdigest()[:10]
        path = folder / f"{name}_{digest}.svg"
        if not path.exists():
            path.write_text(content, encoding="utf-8")
        paths[name] = path.as_posix()
    return paths


def _stylesheet(c: dict) -> str:
    f = _indicator_files(c)
    return f"""
    QCheckBox {{ spacing: 7px; }}
    QCheckBox::indicator {{ width: 16px; height: 16px; }}
    QCheckBox::indicator:unchecked {{ image: url({f['unchecked']}); }}
    QCheckBox::indicator:checked {{ image: url({f['checked']}); }}
    QCheckBox::indicator:disabled {{ image: url({f['disabled']}); }}
    QSpinBox, QDoubleSpinBox {{ padding-right: 20px; }}
    QSpinBox::up-button, QDoubleSpinBox::up-button {{
        subcontrol-origin: border; subcontrol-position: top right; width: 20px;
        border: none; border-left: 1px solid {c['border']}; border-top-right-radius: 5px; }}
    QSpinBox::down-button, QDoubleSpinBox::down-button {{
        subcontrol-origin: border; subcontrol-position: bottom right; width: 20px;
        border: none; border-left: 1px solid {c['border']}; border-bottom-right-radius: 5px; }}
    QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
    QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{ background: {c['hover']}; }}
    QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{ image: url({f['up']}); width: 10px; height: 10px; }}
    QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{ image: url({f['down']}); width: 10px; height: 10px; }}
    QComboBox {{ padding-right: 22px; }}
    QComboBox::drop-down {{ subcontrol-origin: padding; subcontrol-position: center right; width: 22px;
                           border: none; }}
    QComboBox::down-arrow {{ image: url({f['down']}); width: 10px; height: 10px; }}
    QComboBox QAbstractItemView {{ background: {c['base']}; border: 1px solid {c['border']};
                                  selection-background-color: {c['selection']};
                                  selection-color: {c['text']}; }}"""  + f"""
    QMainWindow, QDialog {{ background: {c['window']}; }}
    QToolBar {{ background: {c['panel']}; border: none; border-bottom: 1px solid {c['border']};
               padding: 4px 6px; spacing: 4px; }}
    QToolBar QToolButton {{ padding: 4px 8px; border-radius: 6px; }}
    QToolButton {{ border: 1px solid transparent; border-radius: 6px; padding: 3px; }}
    QToolButton:hover {{ background: {c['hover']}; }}
    QToolButton:checked {{ background: {c['selection']}; border-color: {c['accent']}; }}
    QToolButton::menu-indicator {{ image: none; width: 0; }}
    #SidePanel {{ background: {c['panel']}; border: none; }}
    #PanelTitle {{ color: {c['muted']}; font-weight: 600; letter-spacing: 1px; }}
    #Muted {{ color: {c['muted']}; }}
    #Warning {{ color: {c['warning']}; }}
    #CanvasArea {{ background: {c['canvas_bg']}; border: none; }}
    #PlotBar {{ background: {c['panel']}; border-bottom: 1px solid {c['border']}; }}
    QTabWidget::pane {{ border: none; border-top: 1px solid {c['border']}; }}
    QTabBar::tab {{ padding: 7px 12px; border: none; color: {c['muted']}; background: transparent; }}
    QTabBar::tab:selected {{ color: {c['text']}; border-bottom: 2px solid {c['accent']}; }}
    QTabBar::tab:hover {{ color: {c['text']}; }}
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
        background: {c['base']}; border: 1px solid {c['border']}; border-radius: 5px;
        padding: 4px 6px; min-height: 18px; }}
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{ border-color: {c['accent']}; }}
    QLineEdit[invalid="true"] {{ border: 1px solid {c['error']}; background: {c['error_bg']}; }}
    QListView {{ background: {c['panel']}; border: none; outline: 0; }}
    QPushButton {{ background: {c['base']}; border: 1px solid {c['border']}; border-radius: 6px;
                  padding: 5px 12px; }}
    QPushButton:hover {{ background: {c['hover']}; }}
    QPushButton[primary="true"] {{ background: {c['accent']}; color: {c['accent_text']}; border: none; }}
    #SectionHeader, #SectionHeader:checked, #SectionHeader:hover {{
        font-weight: 600; text-align: left; padding: 8px 2px 4px 2px; background: transparent;
        border: none; border-bottom: 1px solid {c['border']}; border-radius: 0; margin-bottom: 4px; }}
    #SectionHeader:hover {{ color: {c['accent']}; }}
    QScrollArea {{ border: none; background: transparent; }}
    QSplitter::handle {{ background: {c['border']}; }}
    QStatusBar {{ background: {c['panel']}; border-top: 1px solid {c['border']}; }}
    QStatusBar QLabel {{ padding: 0 6px; }}
    """


def apply_theme(app: QApplication, mode: str) -> dict:
    global _current
    _current = dict(DARK if is_dark(mode) else LIGHT)
    c = _current
    app.setStyle("Fusion")
    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: c["window"], QPalette.ColorRole.WindowText: c["text"],
        QPalette.ColorRole.Base: c["base"], QPalette.ColorRole.AlternateBase: c["alt"],
        QPalette.ColorRole.Text: c["text"], QPalette.ColorRole.Button: c["panel"],
        QPalette.ColorRole.ButtonText: c["text"], QPalette.ColorRole.Highlight: c["accent"],
        QPalette.ColorRole.HighlightedText: c["accent_text"], QPalette.ColorRole.ToolTipBase: c["panel"],
        QPalette.ColorRole.ToolTipText: c["text"], QPalette.ColorRole.PlaceholderText: c["muted"],
        QPalette.ColorRole.Link: c["accent"],
    }
    for role, value in roles.items():
        palette.setColor(role, QColor(value))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText, QPalette.ColorRole.WindowText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(c["muted"]))
    app.setPalette(palette)
    app.setStyleSheet(_stylesheet(c))
    return c
