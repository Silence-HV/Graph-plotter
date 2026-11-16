"""Update-Hinweis im Hauptfenster: prüfen, herunterladen, installieren."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QSettings, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel, QMessageBox, QProgressDialog,
                               QPushButton, QWidget)

from .. import VERSION, updates
from ..updates import ReleaseInfo, UpdateError

log = logging.getLogger("graph_plotter.updates")

START_DELAY_MS = 4000           # nach dem Start kurz warten, damit das Programm zuerst flüssig startet
SETTING_ENABLED = "update_check"
SETTING_SKIPPED = "update_skip_tag"


class _Bridge(QObject):
    """Signale aus Hintergrund-Threads sicher in den Hauptthread bringen."""

    found = Signal(object, bool)      # ReleaseInfo, manuell gestartet
    failed = Signal(str, bool)
    progress = Signal(int, int)
    downloaded = Signal(str)
    download_failed = Signal(str)


class UpdateBanner(QFrame):
    """Schmaler Hinweisbalken oben im Fenster."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("UpdateBanner")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        self.label = QLabel()
        self.label.setTextFormat(Qt.TextFormat.PlainText)
        self.update_button = QPushButton("Jetzt aktualisieren")
        self.update_button.setProperty("primary", True)
        self.details_button = QPushButton("Was ist neu?")
        self.skip_button = QPushButton("Diese Version überspringen")
        self.later_button = QPushButton("Später")
        layout.addWidget(self.label, 1)
        for button in (self.update_button, self.details_button, self.skip_button, self.later_button):
            layout.addWidget(button)
        self.hide()


class UpdateController(QObject):
    def __init__(self, window: QWidget, store: QSettings, banner: UpdateBanner):
        super().__init__(window)
        self.window = window
        self.store = store
        self.banner = banner
        self.release: Optional[ReleaseInfo] = None
        self._bridge = _Bridge()
        self._bridge.found.connect(self._found)
        self._bridge.failed.connect(self._failed)
        self._bridge.progress.connect(self._progress)
        self._bridge.downloaded.connect(self._downloaded)
        self._bridge.download_failed.connect(self._download_failed)
        self._checking = False
        self._cancel_download = False
        self._progress_dialog: Optional[QProgressDialog] = None

        banner.update_button.clicked.connect(self.update_now)
        banner.details_button.clicked.connect(self.show_details)
        banner.later_button.clicked.connect(banner.hide)
        banner.skip_button.clicked.connect(self.skip_version)

    # ------------------------------------------------------------------ Einstellungen

    @property
    def enabled(self) -> bool:
        return self.store.value(SETTING_ENABLED, True, type=bool)

    def set_enabled(self, enabled: bool) -> None:
        self.store.setValue(SETTING_ENABLED, enabled)

    def check_on_start(self) -> None:
        """Automatische Prüfung – nur in der ausgelieferten Fassung und wenn nicht abgeschaltet."""
        if self.enabled and updates.install_kind() != "source":
            QTimer.singleShot(START_DELAY_MS, lambda: self.check(manual=False))

    # ------------------------------------------------------------------ Prüfen

    def check(self, manual: bool = True) -> None:
        if self._checking:
            return
        self._checking = True

        def work():
            try:
                self._bridge.found.emit(updates.fetch_latest(), manual)
            except UpdateError as exc:
                self._bridge.failed.emit(str(exc), manual)
            except Exception as exc:  # nichts darf den Programmstart stören
                log.exception("Update-Prüfung fehlgeschlagen")
                self._bridge.failed.emit(f"Unerwarteter Fehler: {exc}", manual)

        threading.Thread(target=work, name="update-check", daemon=True).start()

    def _found(self, info: ReleaseInfo, manual: bool) -> None:
        self._checking = False
        if not updates.is_newer(info.version):
            if manual:
                QMessageBox.information(self.window, "Nach Updates suchen",
                                        f"Sie verwenden die neueste Version ({VERSION}).")
            return
        if not manual and self.store.value(SETTING_SKIPPED, "") == info.tag:
            return
        self.release = info
        kind = updates.install_kind()
        self.banner.label.setText(f"Graph Plotter {info.version_text} ist verfügbar (installiert: {VERSION}).")
        can_install = kind == "installed" and bool(info.setup_url)
        self.banner.update_button.setText("Jetzt aktualisieren" if can_install else "Herunterladen")
        self.banner.update_button.setToolTip(
            "Lädt den Installer, schließt das Programm, installiert und startet es neu." if can_install
            else "Öffnet die Download-Seite im Browser.")
        self.banner.show()

    def _failed(self, message: str, manual: bool) -> None:
        self._checking = False
        log.info("Update-Prüfung: %s", message)
        if manual:
            QMessageBox.warning(self.window, "Nach Updates suchen", message)

    # ------------------------------------------------------------------ Aktionen

    def show_details(self) -> None:
        if self.release and self.release.page_url:
            QDesktopServices.openUrl(QUrl(self.release.page_url))

    def skip_version(self) -> None:
        if self.release:
            self.store.setValue(SETTING_SKIPPED, self.release.tag)
        self.banner.hide()

    def update_now(self) -> None:
        info = self.release
        if info is None:
            return
        if updates.install_kind() != "installed" or not info.setup_url:
            QDesktopServices.openUrl(QUrl(info.page_url))
            return
        if not self._confirm(info):
            return
        self._cancel_download = False
        dialog = QProgressDialog(f"Graph Plotter {info.version_text} wird heruntergeladen …", "Abbrechen",
                                 0, 100, self.window)
        dialog.setWindowTitle("Update")
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        dialog.setAutoClose(False)
        dialog.setAutoReset(False)
        dialog.setMinimumDuration(0)
        dialog.setValue(0)
        dialog.canceled.connect(self._request_cancel)
        dialog.show()
        self._progress_dialog = dialog

        def work():
            try:
                path = updates.download(info, progress=lambda done, total: self._bridge.progress.emit(done, total),
                                        cancelled=lambda: self._cancel_download)
                self._bridge.downloaded.emit(str(path))
            except UpdateError as exc:
                self._bridge.download_failed.emit(str(exc))
            except Exception as exc:
                log.exception("Update-Download fehlgeschlagen")
                self._bridge.download_failed.emit(f"Unerwarteter Fehler: {exc}")

        threading.Thread(target=work, name="update-download", daemon=True).start()

    def _confirm(self, info: ReleaseInfo) -> bool:
        box = QMessageBox(QMessageBox.Icon.Question, "Update installieren",
                          f"Graph Plotter {info.version_text} herunterladen und installieren?\n\n"
                          "Das Programm wird dafür geschlossen und danach neu gestartet. "
                          "Einstellungen und Projekte bleiben erhalten.", parent=self.window)
        save = None
        if getattr(self.window, "datasets", None):
            save = box.addButton("Projekt speichern und aktualisieren", QMessageBox.ButtonRole.AcceptRole)
        go = box.addButton("Aktualisieren", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Abbrechen", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        if clicked is save and save is not None:
            self.window.save_project()
            return True
        return clicked is go

    def _request_cancel(self) -> None:
        self._cancel_download = True

    def _close_progress(self) -> None:
        if self._progress_dialog is not None:
            self._progress_dialog.canceled.disconnect(self._request_cancel)
            self._progress_dialog.reset()   # stoppt den internen Anzeige-Zeitgeber
            self._progress_dialog.hide()
            self._progress_dialog.deleteLater()
            self._progress_dialog = None

    def _progress(self, done: int, total: int) -> None:
        if self._progress_dialog is not None and total > 0:
            self._progress_dialog.setValue(min(100, int(done * 100 / total)))
            self._progress_dialog.setLabelText(
                f"Graph Plotter wird heruntergeladen … {done / 2**20:.1f} von {total / 2**20:.1f} MB")

    def _download_failed(self, message: str) -> None:
        self._close_progress()
        if not self._cancel_download:
            QMessageBox.warning(self.window, "Update", message)

    def _downloaded(self, path: str) -> None:
        self._close_progress()
        from ..app import release_mutex

        log.info("Update heruntergeladen: %s – Installer wird gestartet", path)
        try:
            release_mutex()
            updates.launch_installer(Path(path))
        except OSError as exc:
            QMessageBox.warning(self.window, "Update", f"Installer konnte nicht gestartet werden: {exc}")
            return
        self.window.close()          # speichert Fenster- und Programmeinstellungen
        QApplication.quit()
