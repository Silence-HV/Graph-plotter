"""Längere Arbeiten (Dateien lesen) im Hintergrund ausführen, ohne dass die Oberfläche einfriert."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from PySide6.QtCore import QEventLoop, Qt, QTimer
from PySide6.QtWidgets import QProgressDialog, QWidget

SHOW_AFTER_MS = 400   # kurze Aufgaben ohne Fortschrittsfenster
POLL_MS = 30

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="graph-plotter")


class Cancelled(Exception):
    """Der Nutzer hat die Aufgabe abgebrochen."""


def run_busy(parent: QWidget, label: str, function, *args, **kwargs):
    """``function`` in einem Hintergrund-Thread ausführen und auf das Ergebnis warten.

    Die Ereignisschleife läuft weiter (Fenster bleibt bedienbar und wird neu gezeichnet). Dauert die
    Aufgabe länger als ``SHOW_AFTER_MS``, erscheint ein Fortschrittsfenster mit „Abbrechen“.
    Die Funktion darf keine Qt-Objekte anfassen.

    Raises:
        Cancelled: bei Abbruch (die Aufgabe läuft im Hintergrund zu Ende, ihr Ergebnis wird verworfen).
        Exception: jede Ausnahme der Funktion wird weitergereicht.
    """
    future = _executor.submit(function, *args, **kwargs)
    if future.done():
        return future.result()

    loop = QEventLoop()
    cancelled = []
    dialog: Optional[QProgressDialog] = None

    def on_cancel():
        cancelled.append(True)
        loop.quit()

    def show_dialog():
        # Erst jetzt erzeugen: QProgressDialog startet beim Erzeugen einen eigenen Zeitgeber, der das
        # Fenster nach 4 s von selbst einblendet – auch wenn es inzwischen versteckt wurde.
        nonlocal dialog
        if future.done():
            return
        dialog = QProgressDialog(label, "Abbrechen", 0, 0, parent)
        dialog.setWindowTitle("Bitte warten")
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        dialog.setAutoClose(False)
        dialog.setAutoReset(False)
        dialog.canceled.connect(on_cancel)
        dialog.show()

    def poll():
        if future.done():
            loop.quit()

    timer = QTimer()
    timer.setInterval(POLL_MS)
    timer.timeout.connect(poll)
    show_timer = QTimer()
    show_timer.setSingleShot(True)
    show_timer.timeout.connect(show_dialog)
    timer.start()
    show_timer.start(SHOW_AFTER_MS)
    try:
        loop.exec()
    finally:
        timer.stop()
        show_timer.stop()
        if dialog is not None:
            dialog.canceled.disconnect(on_cancel)
            dialog.reset()   # stoppt den internen Zeitgeber, sonst taucht das Fenster später wieder auf
            dialog.hide()
            dialog.deleteLater()
    if cancelled and not future.done():
        raise Cancelled()
    return future.result()
