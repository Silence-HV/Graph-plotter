"""Einfache Strich-Symbole als SVG, eingefärbt passend zum Farbschema."""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

# Pfade in einem 24×24-Raster; {c} wird durch die Farbe ersetzt.
_PATHS = {
    "open": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    "add": '<path d="M12 5v14M5 12h14"/>',
    "remove": '<path d="M5 12h14"/>',
    "save": '<path d="M5 3h11l3 3v13a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"/>'
            '<path d="M8 3v5h7V3M7 21v-7h10v7"/>',
    "export": '<path d="M12 3v12M7 10l5 5 5-5M4 20h16"/>',
    "copy": '<rect x="9" y="9" width="11" height="12" rx="2"/>'
            '<path d="M5 15H4.5A1.5 1.5 0 0 1 3 13.5v-9A1.5 1.5 0 0 1 4.5 3h9A1.5 1.5 0 0 1 15 4.5V5"/>',
    "theme": '<circle cx="12" cy="12" r="9"/><path d="M12 3a9 9 0 0 0 0 18z" fill="{c}"/>',
    "eye": '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    "eye_off": '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z" opacity="0.45"/>'
               '<path d="M4 4l16 16"/>',
    "home": '<path d="M3 11l9-8 9 8M5 9.5V20h14V9.5"/>',
    "back": '<path d="M15 5l-7 7 7 7"/>',
    "forward": '<path d="M9 5l7 7-7 7"/>',
    "pan": '<path d="M12 3v18M3 12h18M12 3l-3 3M12 3l3 3M12 21l-3-3M12 21l3-3M3 12l3-3M3 12l3 3'
           'M21 12l-3-3M21 12l-3 3"/>',
    "zoom": '<circle cx="10.5" cy="10.5" r="6.5"/><path d="M20 20l-4.8-4.8M8 10.5h5M10.5 8v5"/>',
    "measure": '<circle cx="12" cy="12" r="6"/><path d="M12 2v5M12 17v5M2 12h5M17 12h5"/>',
    "page": '<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4"/>',
    "up": '<path d="M6 15l6-6 6 6"/>',
    "down": '<path d="M6 9l6 6 6-6"/>',
    "chart": '<path d="M4 4v16h16"/><path d="M7 15l4-5 3 3 5-7"/>',
}

_cache: dict[tuple[str, str], QIcon] = {}


def svg(name: str, color: str) -> str:
    body = _PATHS[name].replace("{c}", color)
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
            f'stroke="{color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
            f"{body}</svg>")


def icon(name: str, color: str) -> QIcon:
    key = (name, color)
    if key not in _cache:
        renderer = QSvgRenderer(QByteArray(svg(name, color).encode("utf-8")))
        result = QIcon()
        for size in (16, 24, 32, 48):
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            renderer.render(painter, QRectF(0, 0, size, size))
            painter.end()
            result.addPixmap(pixmap)
        _cache[key] = result
    return _cache[key]
