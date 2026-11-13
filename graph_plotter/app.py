"""Programmstart: Qt-Anwendung, globale Fehlerbehandlung und Logdatei."""

from __future__ import annotations

import logging
import os
import sys
import traceback
from pathlib import Path

import matplotlib

matplotlib.use("Qt5Agg")

from PyQt5.QtCore import Qt  # noqa: E402
from PyQt5.QtWidgets import QApplication, QMessageBox  # noqa: E402

from . import VERSION  # noqa: E402

log = logging.getLogger("graph_plotter")


def log_file() -> Path:
    base = Path(os.environ.get("APPDATA") or Path.home()) / "GraphPlotter"
    base.mkdir(parents=True, exist_ok=True)
    return base / "graphplotter.log"


def _setup_logging() -> Path | None:
    try:
        path = log_file()
        logging.basicConfig(filename=path, level=logging.INFO, encoding="utf-8",
                            format="%(asctime)s %(levelname)s %(name)s: %(message)s")
        return path
    except OSError:
        logging.basicConfig(level=logging.INFO)
        return None


def _install_excepthook(log_path: Path | None) -> None:
    """Unbehandelte Fehler protokollieren und anzeigen statt sie (in der .exe) stillschweigend zu verlieren."""

    def handle(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        details = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        log.error("Unbehandelter Fehler:\n%s", details)
        if sys.__stderr__ is not None:  # in der .exe (--windowed) gibt es kein stderr
            print(details, file=sys.__stderr__, flush=True)
        if QApplication.instance() is not None:
            box = QMessageBox(QMessageBox.Critical, "Unerwarteter Fehler",
                              f"Es ist ein unerwarteter Fehler aufgetreten:\n\n{exc_value}")
            if log_path is not None:
                box.setInformativeText(f"Details wurden gespeichert in:\n{log_path}")
            box.setDetailedText(details)
            box.exec_()
        else:
            sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = handle


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    log_path = _setup_logging()
    log.info("Graph Plotter v%s gestartet", VERSION)
    _install_excepthook(log_path)

    global _app, _window
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    # Modulweit halten: Würde die Anwendung beim Verlassen von main() abgebaut, stürzt ein
    # Fehlerdialog im excepthook ab (Zugriff auf ein zerstörtes Qt-Objekt).
    _app = QApplication.instance() or QApplication(argv)

    from .ui.main_window import MainWindow

    _window = MainWindow()
    _window.show()
    # Dateien von der Kommandozeile bzw. „Öffnen mit“ laden
    if len(argv) > 1:
        _window.open_paths(argv[1:])
    return _app.exec_()


_app = None
_window = None
