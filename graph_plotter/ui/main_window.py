"""Hauptfenster des Graph Plotters."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QByteArray, QMimeData, QSettings, QSize, Qt, QTimer
from PySide6.QtGui import (QAction, QActionGroup, QGuiApplication, QImage, QKeySequence,
                           QShortcut)
from PySide6.QtWidgets import (QApplication, QComboBox, QDialog, QFileDialog, QHBoxLayout,
                               QLabel, QMainWindow, QMenu, QMessageBox, QSizePolicy, QSplitter,
                               QTabWidget, QToolBar, QToolButton, QVBoxLayout, QWidget)

from .. import VERSION
from ..exporting import FORMATS, export_bytes, export_plot, normalize_extension, options_from_settings
from ..loaders import (CSV_EXTENSIONS, EXCEL_EXTENSIONS, LoadError, default_spec, is_supported,
                       load_datasets, read_table)
from ..model import DEFAULT_COLORS, Dataset
from ..plotting import PlotError, PlotSettings, render, with_view
from ..presets import PRESETS, matching_preset
from ..project import PROJECT_EXTENSION, load_project, save_project
from . import icons, theme
from .dataset_list import DatasetListView, DatasetModel
from .import_dialog import ImportDialog
from .panels import AppearancePanel, AxesPanel, DatasetEditor, ExportPanel, scrollable
from .plot_view import PlotView

EXPORT_FILTERS = [(f"{text} (*.{ext})", ext) for ext, (text, _) in FORMATS.items()]
LIVE_DELAY_MS = 250
MAX_RECENT = 10
EMPTY_HINT = "Dateien hierher ziehen\noder über „Öffnen“ laden"


class MainWindow(QMainWindow):
    def __init__(self, store: Optional[QSettings] = None):
        super().__init__()
        self.store = store if store is not None else QSettings("GraphPlotter", "GraphPlotter")
        self.datasets: list[Dataset] = []
        self._project_path: Optional[str] = None
        self._has_plot = False
        self._loading = False
        self._summary = ""
        self._last_dir = str(self.store.value("last_dir", str(Path.home())))
        self._theme_mode = str(self.store.value("theme", "system"))
        self.setAcceptDrops(True)
        self.resize(1500, 900)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(LIVE_DELAY_MS)
        self._timer.timeout.connect(self.replot)

        self.model = DatasetModel(self.datasets, self)
        self.model.edited.connect(self._list_edited)

        self._build_actions()
        self._build_toolbar()
        self._build_central()
        self._build_statusbar()
        self._restore_state()
        self.set_theme(self._theme_mode, save=False)
        QGuiApplication.styleHints().colorSchemeChanged.connect(self._system_scheme_changed)

        self._update_title()
        self._sync_preset()
        self._update_page_size()
        self.replot()

    # ================================================================== Aufbau

    def _action(self, text: str, slot, shortcut=None, tip: str = "") -> QAction:
        action = QAction(text, self)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        action.setToolTip(tip or text)
        action.triggered.connect(slot)
        self.addAction(action)
        return action

    def _build_actions(self) -> None:
        self.act_load = self._action("Dateien laden…", lambda: self.choose_files(), "Ctrl+O",
                                     "CSV-, Text- und Excel-Dateien laden (Strg+O)")
        self.act_load_stats = self._action("Als Messwiederholungen laden…",
                                           lambda: self.choose_files(statistics=True),
                                           tip="Alle Y-Spalten einer Datei zu Mittelwert ± Fehler zusammenfassen")
        self.act_open_project = self._action("Projekt öffnen…", lambda: self.open_project(), "Ctrl+Shift+O")
        self.act_import_dialog = QAction("Importdialog anzeigen", self)
        self.act_import_dialog.setCheckable(True)
        self.act_import_dialog.setChecked(self.store.value("import_dialog", True, type=bool))
        self.act_save = self._action("Speichern", lambda: self.save_project(), "Ctrl+S",
                                     "Projekt speichern: Dateien und alle Einstellungen (Strg+S)")
        self.act_save_as = self._action("Speichern unter…", lambda: self.save_project(save_as=True),
                                        "Ctrl+Shift+S")
        self.act_export = self._action("Komplette Grafik exportieren…", lambda: self.export(), "Ctrl+E",
                                       "Plot als PDF, SVG, PNG … speichern (Strg+E)")
        self.act_export_view = self._action("Aktuellen Ausschnitt exportieren…",
                                            lambda: self.export(view_only=True), "Ctrl+Shift+E",
                                            "Nur den gezoomten/verschobenen Bereich exportieren (Strg+Umschalt+E)")
        self.act_copy = self._action("Komplette Grafik kopieren", lambda: self.copy_plot(), "Ctrl+Shift+C",
                                     "Plot in die Zwischenablage kopieren – zum Einfügen in Word/PowerPoint "
                                     "(Strg+Umschalt+C)")
        self.act_copy_view = self._action("Aktuellen Ausschnitt kopieren", lambda: self.copy_plot(view_only=True),
                                          tip="Nur den gezoomten/verschobenen Bereich kopieren")
        self.act_apply_view = self._action("Ausschnitt als Achsengrenzen übernehmen", self.apply_view,
                                           tip="Aktuellen Zoom dauerhaft in die Min/Max-Felder eintragen")
        for action in (self.act_export_view, self.act_copy_view, self.act_apply_view):
            action.setEnabled(False)

    def _build_toolbar(self) -> None:
        bar = QToolBar("Werkzeuge")
        bar.setMovable(False)
        bar.setIconSize(QSize(18, 18))
        bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(bar)
        self.toolbar = bar

        self.recent_menu = QMenu("Zuletzt geöffnet", self)
        open_menu = QMenu(self)
        for action in (self.act_load, self.act_load_stats, self.act_open_project):
            open_menu.addAction(action)
        open_menu.addMenu(self.recent_menu)
        open_menu.addSeparator()
        open_menu.addAction(self.act_import_dialog)
        self.open_button = self._menu_button("Öffnen", open_menu, self.choose_files,
                                             "Dateien laden (Strg+O) – Pfeil für weitere Optionen")
        bar.addWidget(self.open_button)

        save_menu = QMenu(self)
        save_menu.addAction(self.act_save_as)
        self.save_button = self._menu_button("Speichern", save_menu, lambda: self.save_project(),
                                             self.act_save.toolTip())
        bar.addWidget(self.save_button)
        bar.addSeparator()
        export_menu = QMenu(self)
        export_menu.addAction(self.act_export)
        export_menu.addAction(self.act_export_view)
        export_menu.addSeparator()
        export_menu.addAction(self.act_apply_view)
        self.export_button = self._menu_button("Exportieren", export_menu, lambda: self.export(),
                                               "Komplette Grafik exportieren (Strg+E) – Pfeil: nur den "
                                               "aktuellen Zoom-Ausschnitt")
        bar.addWidget(self.export_button)
        copy_menu = QMenu(self)
        copy_menu.addAction(self.act_copy)
        copy_menu.addAction(self.act_copy_view)
        self.copy_button = self._menu_button("Kopieren", copy_menu, lambda: self.copy_plot(),
                                             "In die Zwischenablage kopieren (Strg+Umschalt+C) – Pfeil: nur "
                                             "den aktuellen Zoom-Ausschnitt")
        bar.addWidget(self.copy_button)
        bar.addSeparator()

        preset_label = QLabel("  Vorlage ")
        preset_label.setObjectName("Muted")
        bar.addWidget(preset_label)
        self.preset_combo = QComboBox()
        self.preset_combo.addItem("Benutzerdefiniert", None)
        for key, preset in PRESETS.items():
            self.preset_combo.addItem(preset.name, key)
        self.preset_combo.setToolTip("Setzt Schriftgrößen und Exportgröße für den gewählten Zweck")
        self.preset_combo.activated.connect(self._preset_chosen)
        bar.addWidget(self.preset_combo)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        bar.addWidget(spacer)

        theme_menu = QMenu(self)
        group = QActionGroup(self)
        self.theme_actions = {}
        for mode, text in theme.THEME_MODES.items():
            action = QAction(text, self, checkable=True)
            action.triggered.connect(lambda _=False, m=mode: self.set_theme(m))
            group.addAction(action)
            theme_menu.addAction(action)
            self.theme_actions[mode] = action
        theme_menu.addSeparator()
        theme_menu.addAction("Über Graph Plotter…", self._about)
        self.theme_button = QToolButton()
        self.theme_button.setText("Farbschema")
        self.theme_button.setToolTip("Farbschema und Programminfo")
        self.theme_button.setMenu(theme_menu)
        self.theme_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.theme_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        bar.addWidget(self.theme_button)

    @staticmethod
    def _menu_button(text: str, menu: QMenu, slot, tip: str) -> QToolButton:
        button = QToolButton()
        button.setText(text)
        button.setToolTip(tip)
        button.setMenu(menu)
        button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.clicked.connect(lambda: slot())
        return button

    def _build_central(self) -> None:
        # Links: Datensätze
        left = QWidget()
        left.setObjectName("SidePanel")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(8, 8, 8, 8)
        header = QHBoxLayout()
        title = QLabel("DATEN")
        title.setObjectName("PanelTitle")
        header.addWidget(title)
        header.addStretch()
        self.list_buttons = {}
        for key, tip, slot in (("add", "Dateien laden (Strg+O)", lambda: self.choose_files()),
                               ("remove", "Ausgewählte entfernen (Entf)", self.remove_selected),
                               ("up", "Nach oben (Strg+↑)", lambda: self.move_selected(-1)),
                               ("down", "Nach unten (Strg+↓)", lambda: self.move_selected(1))):
            button = QToolButton()
            button.setToolTip(tip)
            button.setAutoRaise(True)
            button.clicked.connect(slot)
            header.addWidget(button)
            self.list_buttons[key] = button
        left_layout.addLayout(header)
        self.list_view = DatasetListView(self.model)
        self.list_view.selectionModel().selectionChanged.connect(self._selection_changed)
        left_layout.addWidget(self.list_view, 1)
        for key, slot in ((QKeySequence.StandardKey.Delete, self.remove_selected),
                          ("Ctrl+Up", lambda: self.move_selected(-1)),
                          ("Ctrl+Down", lambda: self.move_selected(1))):
            shortcut = QShortcut(QKeySequence(key), self.list_view)
            shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
            shortcut.activated.connect(slot)

        # Mitte: Plot
        self.plot_view = PlotView()
        self.plot_view.label_lookup = self._label_for
        self.plot_view.hover.connect(lambda text: self.coords_label.setText(text))
        self.plot_view.measured.connect(self._measured)
        self.plot_view.viewChanged.connect(self._view_changed)
        self.plot_view.applyViewRequested.connect(self.apply_view)

        # Rechts: Eigenschaften
        self.editor = DatasetEditor()
        self.axes_panel = AxesPanel()
        self.appearance = AppearancePanel()
        self.export_panel = ExportPanel()
        self.tabs = QTabWidget()
        self.tabs.setObjectName("SidePanel")
        self.tabs.setDocumentMode(True)
        self.tabs.addTab(scrollable(self.editor), "Datensatz")
        self.tabs.addTab(scrollable(self.axes_panel), "Achsen")
        self.tabs.addTab(scrollable(self.appearance), "Darstellung")
        self.tabs.addTab(scrollable(self.export_panel), "Export")

        self.editor.changed.connect(self._editor_changed)
        self.axes_panel.changed.connect(self.schedule)
        self.appearance.changed.connect(self._appearance_changed)
        self.export_panel.changed.connect(self._export_changed)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.addWidget(left)
        self.splitter.addWidget(self.plot_view)
        self.splitter.addWidget(self.tabs)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([290, 880, 360])
        self.splitter.setChildrenCollapsible(False)
        left.setMinimumWidth(220)
        self.tabs.setMinimumWidth(320)
        self.setCentralWidget(self.splitter)

    def _build_statusbar(self) -> None:
        bar = self.statusBar()
        bar.setSizeGripEnabled(False)
        self.status_label = QLabel()
        self.warning_label = QLabel()
        self.warning_label.setObjectName("Warning")
        self.coords_label = QLabel()
        self.coords_label.setObjectName("Muted")
        bar.addWidget(self.status_label, 1)
        bar.addWidget(self.warning_label)
        bar.addPermanentWidget(self.coords_label)

    def refresh_icons(self) -> None:
        color = theme.colors()["text"]
        self.open_button.setIcon(icons.icon("open", color))
        self.save_button.setIcon(icons.icon("save", color))
        self.export_button.setIcon(icons.icon("export", color))
        self.copy_button.setIcon(icons.icon("copy", color))
        self.act_apply_view.setIcon(icons.icon("crop", color))
        self.theme_button.setIcon(icons.icon("theme", color))
        for key, button in self.list_buttons.items():
            button.setIcon(icons.icon(key, color))
        self.plot_view.refresh_icons()
        self.setWindowIcon(icons.icon("chart", theme.colors()["accent"]))

    # ================================================================== Zustand

    def _restore_state(self) -> None:
        geometry = self.store.value("geometry")
        if isinstance(geometry, QByteArray):
            self.restoreGeometry(geometry)
        splitter = self.store.value("splitter")
        if isinstance(splitter, QByteArray):
            self.splitter.restoreState(splitter)
        self._rebuild_recent()

    def closeEvent(self, event) -> None:
        self.store.setValue("geometry", self.saveGeometry())
        self.store.setValue("splitter", self.splitter.saveState())
        self.store.setValue("import_dialog", self.act_import_dialog.isChecked())
        self.store.setValue("last_dir", self._last_dir)
        self.store.sync()
        super().closeEvent(event)

    def _recent(self) -> list[str]:
        value = self.store.value("recent", [])
        if isinstance(value, str):
            value = [value]
        return [str(v) for v in (value or [])]

    def _add_recent(self, path: str) -> None:
        path = str(Path(path).resolve())
        recent = [p for p in self._recent() if p != path]
        self.store.setValue("recent", [path] + recent[:MAX_RECENT - 1])
        self._rebuild_recent()

    def _rebuild_recent(self) -> None:
        self.recent_menu.clear()
        recent = [p for p in self._recent() if Path(p).exists()]
        if not recent:
            self.recent_menu.addAction("(keine)").setEnabled(False)
            return
        for path in recent:
            action = self.recent_menu.addAction(Path(path).name)
            action.setToolTip(path)
            action.triggered.connect(lambda _=False, p=path: self.open_paths([p]))
        self.recent_menu.addSeparator()
        self.recent_menu.addAction("Liste leeren", self._clear_recent)

    def _clear_recent(self) -> None:
        self.store.setValue("recent", [])
        self._rebuild_recent()

    def set_theme(self, mode: str, save: bool = True) -> None:
        if mode not in theme.THEME_MODES:
            mode = "system"
        self._theme_mode = mode
        theme.apply_theme(QApplication.instance(), mode)
        self.theme_actions[mode].setChecked(True)
        self.refresh_icons()
        self.list_view.viewport().update()
        if save:
            self.store.setValue("theme", mode)

    def _system_scheme_changed(self, *_args) -> None:
        if self._theme_mode == "system":
            self.set_theme("system", save=False)

    def _update_title(self) -> None:
        name = Path(self._project_path).name if self._project_path else "Unbenannt"
        self.setWindowTitle(f"{name} – Graph Plotter {VERSION}")

    def _about(self) -> None:
        from ..app import log_file
        QMessageBox.about(self, "Über Graph Plotter",
                          f"<b>Graph Plotter {VERSION}</b><br>Messdaten aus CSV- und Excel-Dateien darstellen."
                          f"<br><br>Protokolldatei:<br>{log_file()}")

    # ================================================================== Einstellungen

    def collect_settings(self) -> PlotSettings:
        """Einstellungen aus der Oberfläche. Raises ValueError mit allen ungültigen Feldern."""
        x, y, y2 = self.axes_panel.axes()
        settings = PlotSettings(x=x, y=y, y2=y2, y2_enabled=self.axes_panel.y2_check.isChecked())
        self.appearance.apply_to(settings)
        settings.export = self.export_panel.settings()
        return settings

    def load_settings(self, settings: PlotSettings) -> None:
        self._loading = True
        try:
            self.axes_panel.set_axes(settings)
            self.appearance.load(settings)
            self.export_panel.load(settings.export)
        finally:
            self._loading = False
        self._sync_preset()
        self._update_page_size()

    def _current_preset_values(self) -> PlotSettings:
        s = PlotSettings()
        self.appearance.apply_to(s)
        s.export = self.export_panel.settings()
        return s

    def _sync_preset(self) -> None:
        key = matching_preset(self._current_preset_values())
        self.preset_combo.blockSignals(True)
        self.preset_combo.setCurrentIndex(max(0, self.preset_combo.findData(key)))
        self.preset_combo.blockSignals(False)

    def _preset_chosen(self, index: int) -> None:
        key = self.preset_combo.itemData(index)
        if key is None:
            return
        preset = PRESETS[key]
        self._loading = True
        try:
            self.appearance.label_size.setValue(int(preset.label_fontsize))
            self.appearance.tick_size.setValue(int(preset.tick_fontsize))
            self.appearance.legend_size.setValue(int(preset.legend_fontsize))
            self.export_panel.width.setValue(preset.width_cm)
            self.export_panel.height.setValue(preset.height_cm)
        finally:
            self._loading = False
        self._update_page_size()
        self.statusBar().showMessage(f"Vorlage „{preset.name}“: Schrift {preset.label_fontsize}/"
                                     f"{preset.tick_fontsize}/{preset.legend_fontsize} pt, Export "
                                     f"{preset.width_cm:g} × {preset.height_cm:g} cm".replace(".", ","), 5000)
        self.schedule()

    def _appearance_changed(self) -> None:
        if not self._loading:
            self._sync_preset()
        self.schedule()

    def _export_changed(self) -> None:
        if self._loading:
            return
        self._sync_preset()
        self._update_page_size()

    def _update_page_size(self) -> None:
        e = self.export_panel.settings()
        self.plot_view.set_page_size(e.width_cm / 2.54, e.height_cm / 2.54)

    # ================================================================== Datensätze

    def _label_for(self, index: int) -> str:
        return self.datasets[index].display_label if 0 <= index < len(self.datasets) else f"G{index + 1}"

    def _selected(self) -> list[Dataset]:
        return [self.datasets[r] for r in self.list_view.selected_rows() if r < len(self.datasets)]

    def _selection_changed(self, *_args) -> None:
        rows = self.list_view.selected_rows()
        self.editor.set_targets([self.datasets[r] for r in rows],
                                [self.model.color_of(r) for r in rows])

    def _editor_changed(self) -> None:
        for row in self.list_view.selected_rows():
            self.model.row_changed(row)
        self.schedule()

    def _list_edited(self) -> None:
        self._selection_changed()
        self.schedule()

    def _next_color(self) -> str:
        used = {d.color for d in self.datasets}
        for color in DEFAULT_COLORS:
            if color not in used:
                return color
        return DEFAULT_COLORS[len(self.datasets) % len(DEFAULT_COLORS)]

    def remove_selected(self) -> None:
        rows = self.list_view.selected_rows()
        if not rows:
            self.statusBar().showMessage("Zum Entfernen zuerst Datensätze in der Liste auswählen.", 4000)
            return
        for row in reversed(rows):
            del self.datasets[row]
        self.model.refresh()
        if self.datasets:
            self.list_view.select_rows([min(rows[0], len(self.datasets) - 1)])
        self._selection_changed()
        self.replot()

    def remove_all(self) -> None:
        if not self.datasets:
            return
        if QMessageBox.question(self, "Alle entfernen", "Alle Datensätze entfernen?") != QMessageBox.StandardButton.Yes:
            return
        self.datasets.clear()
        self.model.refresh()
        self._selection_changed()
        self.replot()

    def move_selected(self, step: int) -> None:
        rows = self.list_view.selected_rows()
        if not rows or (step < 0 and rows[0] == 0) or (step > 0 and rows[-1] == len(self.datasets) - 1):
            return
        for row in (rows if step < 0 else list(reversed(rows))):
            self.datasets[row], self.datasets[row + step] = self.datasets[row + step], self.datasets[row]
        self.model.refresh()
        self.list_view.select_rows([r + step for r in rows])
        self.schedule()

    # ================================================================== Laden

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        self.dragEnterEvent(event)

    def dropEvent(self, event) -> None:
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.toLocalFile()]
        event.acceptProposedAction()
        self.open_paths(paths)

    def open_paths(self, paths: list[str]) -> None:
        """Projektdateien öffnen, Datendateien hinzufügen."""
        projects = [p for p in paths if p.lower().endswith(PROJECT_EXTENSION)]
        data_files = [p for p in paths if not p.lower().endswith(PROJECT_EXTENSION)]
        if projects:
            self.open_project(projects[0])
        if data_files:
            self.add_files(data_files)

    def choose_files(self, statistics: bool = False) -> None:
        patterns = " ".join(f"*{ext}" for ext in CSV_EXTENSIONS + EXCEL_EXTENSIONS)
        filters = (f"Messdaten ({patterns});;"
                   f"CSV/Text ({' '.join('*' + e for e in CSV_EXTENSIONS)});;"
                   f"Excel ({' '.join('*' + e for e in EXCEL_EXTENSIONS)});;"
                   "Alle Dateien (*)")
        title = "Dateien als Messwiederholungen laden" if statistics else "Dateien laden"
        paths, _ = QFileDialog.getOpenFileNames(self, title, self._last_dir, filters)
        if paths:
            self._last_dir = str(Path(paths[0]).parent)
            self.add_files(paths, statistics=statistics)

    def add_files(self, paths: list[str], statistics: bool = False) -> None:
        errors: list[str] = []
        notes: list[str] = []
        first_new = len(self.datasets)
        for path in paths:
            name = Path(path).name
            if not is_supported(path):
                errors.append(f"{name}: Dateityp wird nicht unterstützt.")
                continue
            try:
                table = read_table(path)
                spec = default_spec(path, table, statistics=statistics)
                if self.act_import_dialog.isChecked():
                    dialog = ImportDialog(self, path, table, spec)
                    if dialog.exec() != QDialog.DialogCode.Accepted:
                        continue
                    spec, table = dialog.spec(), dialog.table
                result = load_datasets(spec, table)
            except LoadError as exc:
                errors.append(f"{name}: {exc}")
                continue
            if not result.datasets:
                errors.append(f"{name}: keine gültigen Zahlendaten gefunden.")
                continue
            if any(d.spec and Path(d.spec.path) == Path(path) for d in self.datasets[:first_new]):
                notes.append(f"{name}: Diese Datei war bereits geladen.")
            for ds in result.datasets:
                ds.color = self._next_color()
                self.datasets.append(ds)
            self._add_recent(path)
            if result.skipped_rows:
                notes.append(f"{name}: {result.skipped_rows} Zeile(n) mit ungültigem X-Wert übersprungen.")
            if result.empty_columns:
                notes.append(f"{name}: Spalten ohne gültige Werte ignoriert: {', '.join(result.empty_columns)}.")
            if result.x_is_time:
                notes.append(f"{name}: X-Werte sind Datum/Uhrzeit – dargestellt als Sekunden ab dem ersten Wert.")

        if len(self.datasets) > first_new:
            self.model.refresh()
            self.list_view.select_rows(list(range(first_new, len(self.datasets))))
            self._selection_changed()
            self.replot()
        if errors:
            QMessageBox.warning(self, "Laden", "\n".join(errors + ([""] + notes if notes else [])))
        elif notes:
            QMessageBox.information(self, "Laden", "\n".join(notes))

    # ================================================================== Plotten

    def schedule(self) -> None:
        """Live-Vorschau: kurz nach der letzten Änderung neu zeichnen."""
        if not self._loading:
            self._timer.start()

    def replot(self) -> bool:
        self._timer.stop()
        if not self.datasets:
            self.plot_view.show_message(EMPTY_HINT)
            self._has_plot = False
            self.axes_panel.set_auto({})
            self._set_status("Keine Daten geladen.", [])
            return False
        try:
            settings = self.collect_settings()
        except ValueError as exc:
            self.warning_label.setText("⚠ Ungültige Eingabe – rot markierte Felder korrigieren")
            self.warning_label.setToolTip(str(exc))
            return False
        try:
            result = render(self.plot_view.figure, self.datasets, settings)
        except PlotError as exc:
            self.plot_view.show_message(str(exc).splitlines()[0])
            self._has_plot = False
            self._set_status("", str(exc).splitlines()[1:])
            return False
        self.plot_view.after_render(result.limits)
        self._has_plot = True
        self.axes_panel.set_auto(result.limits)
        visible = [d for d in self.datasets if d.visible]
        points = f"{sum(d.n_points for d in visible):,}".replace(",", ".")
        self._set_status(f"{len(visible)} von {len(self.datasets)} Datensätzen · {points} Punkte",
                         result.warnings)
        return True

    def _set_status(self, summary: str, warnings: list[str]) -> None:
        self._summary = summary
        self.status_label.setText(summary)
        warnings = [w for w in warnings if w]
        self.warning_label.setText(f"⚠ {len(warnings)} Hinweis(e) – Maus hierher für Details" if warnings else "")
        self.warning_label.setToolTip("\n".join(warnings))

    def _measured(self, text: str) -> None:
        self.status_label.setText(text or self._summary)

    # ================================================================== Ausschnitt (Zoom)

    def _view_changed(self, zoomed: bool) -> None:
        for action in (self.act_export_view, self.act_copy_view, self.act_apply_view):
            action.setEnabled(zoomed)
        if zoomed:
            self.statusBar().showMessage("Ausschnitt aktiv – exportieren/kopieren über den Pfeil an "
                                         "„Exportieren“ bzw. „Kopieren“, dauerhaft übernehmen mit dem "
                                         "Zuschneiden-Symbol über dem Plot.", 6000)

    def apply_view(self) -> None:
        """Aktuellen Zoom in die Min/Max-Felder eintragen (bleibt beim Neuzeichnen erhalten)."""
        if not self.plot_view.is_zoomed():
            return
        view = self.plot_view.view_limits()
        editors = {"x": self.axes_panel.x, "y": self.axes_panel.y, "y2": self.axes_panel.y2}
        for key, (lo, hi) in view.items():
            if key == "y2" and not self.axes_panel.y2_check.isChecked():
                continue
            lo, hi = sorted((lo, hi))
            editors[key].min_edit.set_value(float(f"{lo:.6g}"))
            editors[key].max_edit.set_value(float(f"{hi:.6g}"))
        self.tabs.setCurrentWidget(self.tabs.widget(1))  # Achsen-Tab zeigen
        self.statusBar().showMessage("Ausschnitt als Achsengrenzen übernommen. Zurück zur ganzen Grafik: "
                                     "Min/Max-Felder leeren.", 6000)
        self.replot()

    # ================================================================== Export

    # ================================================================== Export

    def _settings_or_warn(self) -> Optional[PlotSettings]:
        try:
            return self.collect_settings()
        except ValueError as exc:
            QMessageBox.warning(self, "Ungültige Eingaben", f"Bitte diese Felder korrigieren:\n\n{exc}")
            return None

    def _export_settings(self, view_only: bool) -> Optional[PlotSettings]:
        """Einstellungen für Export/Kopieren; mit ``view_only`` auf den aktuellen Zoom begrenzt."""
        settings = self._settings_or_warn()
        if settings is None:
            return None
        if view_only:
            if not self.plot_view.is_zoomed():
                QMessageBox.information(self, "Ausschnitt", "Es ist kein Ausschnitt aktiv. Zuerst mit der Lupe "
                                                            "oder dem Verschieben-Werkzeug zoomen.")
                return None
            settings = with_view(settings, self.plot_view.view_limits())
        return settings

    def export(self, view_only: bool = False) -> None:
        if not self._has_plot:
            QMessageBox.warning(self, "Export", "Es gibt noch keinen Plot zum Exportieren.")
            return
        settings = self._export_settings(view_only)
        if settings is None:
            return
        filters = ";;".join(f for f, _ in EXPORT_FILTERS)
        stem = Path(self._project_path).stem if self._project_path else "plot"
        suggested = str(Path(self._last_dir) / (f"{stem}_ausschnitt" if view_only else stem))
        title = "Ausschnitt exportieren" if view_only else "Plot exportieren"
        path, chosen = QFileDialog.getSaveFileName(self, title, suggested, filters)
        if not path:
            return
        ext = normalize_extension(path)
        if ext not in FORMATS:
            ext = next((e for f, e in EXPORT_FILTERS if f == chosen), "pdf")
            path += f".{ext}"
        self._last_dir = str(Path(path).parent)

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            result = export_plot(path, self.datasets, settings, options_from_settings(settings.export))
        except (PlotError, OSError, ValueError) as exc:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "Fehler beim Export", str(exc))
            return
        QApplication.restoreOverrideCursor()

        size_kb = Path(path).stat().st_size / 1024
        size_text = f"{size_kb / 1024:.1f} MB" if size_kb > 1024 else f"{size_kb:.0f} KB"
        what = "Ausschnitt" if view_only else "Plot"
        message = (f"{what} exportiert ({size_text}, {settings.export.width_cm:g} × "
                   f"{settings.export.height_cm:g} cm):\n{path}")
        if result.reductions:
            message += "\n\nDatenreduktion:\n" + "\n".join(result.reductions)
        QMessageBox.information(self, "Export", message)

    def copy_plot(self, view_only: bool = False) -> None:
        if not self._has_plot:
            self.statusBar().showMessage("Es gibt noch keinen Plot zum Kopieren.", 4000)
            return
        settings = self._export_settings(view_only)
        if settings is None:
            return
        options = options_from_settings(settings.export)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            png = export_bytes("png", self.datasets, settings, options)
            svg = export_bytes("svg", self.datasets, settings, options)
        except (PlotError, ValueError) as exc:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "Kopieren", str(exc))
            return
        QApplication.restoreOverrideCursor()
        mime = QMimeData()
        mime.setImageData(QImage.fromData(png, "PNG"))
        mime.setData("image/png", QByteArray(png))
        mime.setData("image/svg+xml", QByteArray(svg))
        QApplication.clipboard().setMimeData(mime)
        e = settings.export
        what = "Ausschnitt" if view_only else "Plot"
        self.statusBar().showMessage(f"{what} kopiert ({e.width_cm:g} × {e.height_cm:g} cm, {e.dpi} dpi) – "
                                     "in Word/PowerPoint mit Strg+V einfügen.", 6000)

    # ================================================================== Projekt

    def save_project(self, save_as: bool = False) -> None:
        if not self.datasets:
            QMessageBox.information(self, "Projekt speichern", "Es sind keine Datensätze geladen.")
            return
        settings = self._settings_or_warn()
        if settings is None:
            return
        path = self._project_path
        if save_as or not path:
            suggested = path or str(Path(self._last_dir) / f"Projekt{PROJECT_EXTENSION}")
            path, _ = QFileDialog.getSaveFileName(self, "Projekt speichern", suggested,
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
        self._project_path = path
        self._last_dir = str(Path(path).parent)
        self._add_recent(path)
        self._update_title()
        self.statusBar().showMessage(f"Projekt gespeichert: {path}", 5000)

    def open_project(self, path: Optional[str] = None) -> None:
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "Projekt öffnen", self._last_dir,
                                                  f"Graph-Plotter-Projekt (*{PROJECT_EXTENSION})")
            if not path:
                return
        if self.datasets and QMessageBox.question(
                self, "Projekt öffnen",
                "Die aktuell geladenen Datensätze werden ersetzt. Fortfahren?") != QMessageBox.StandardButton.Yes:
            return
        try:
            project = load_project(path)
        except LoadError as exc:
            QMessageBox.critical(self, "Projekt öffnen", str(exc))
            return
        self._project_path = path
        self._last_dir = str(Path(path).parent)
        self.datasets[:] = project.datasets  # Liste bleibt dieselbe (das Modell hält sie)
        self.model.refresh()
        self.load_settings(project.settings)
        self._selection_changed()
        self._add_recent(path)
        self._update_title()
        self.replot()
        if project.problems:
            QMessageBox.warning(self, "Projekt öffnen", "Nicht alles konnte geladen werden:\n\n"
                                + "\n".join(project.problems))
