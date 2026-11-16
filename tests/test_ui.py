"""Tests der Oberfläche (ohne sichtbares Fenster)."""

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyside6")
pytest.importorskip("PySide6")

import matplotlib  # noqa: E402

matplotlib.use("QtAgg")

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from graph_plotter.loaders import default_spec, read_table  # noqa: E402
from graph_plotter.ui import main_window as mw  # noqa: E402
from graph_plotter.ui.import_dialog import ImportDialog  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app, tmp_path, monkeypatch):
    for name in ("warning", "information", "critical"):
        monkeypatch.setattr(mw.QMessageBox, name, staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(mw.QMessageBox, "question",
                        staticmethod(lambda *a, **k: mw.QMessageBox.StandardButton.Yes))
    store = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    win = mw.MainWindow(store)
    win.act_import_dialog.setChecked(False)
    yield win
    win.close()


@pytest.fixture
def csv_file(tmp_path):
    path = tmp_path / "messung.csv"
    path.write_text("Zeit;U1;U2;U3\n0;1,0;1,2;0,9\n1;2,0;2,1;1,9\n2;3,0;3,3;2,8\n", encoding="utf-8")
    return str(path)


def test_empty_state(window):
    assert not window._has_plot
    assert "hierher ziehen" in window.plot_view.figure.texts[0].get_text()


def test_load_plots_immediately_and_keeps_styles_on_remove(window, csv_file):
    window.add_files([csv_file])
    assert len(window.datasets) == 3 and window._has_plot
    assert len({d.color for d in window.datasets}) == 3
    window.datasets[2].label = "Dritte"
    window.datasets[2].color = "#000000"
    window.list_view.select_rows([0])
    window.remove_selected()
    assert window.datasets[-1].display_label == "Dritte"
    assert window.datasets[-1].color == "#000000"
    assert window.model.rowCount() == 2


def test_live_update_and_invalid_input(window, csv_file):
    window.add_files([csv_file])
    window.appearance.title.setText("Versuch")
    assert window._timer.isActive()
    assert window.replot()
    assert window.plot_view.figure.axes[0].get_title() == "Versuch"

    window.axes_panel.x.min_edit.setText("abc")
    assert not window.replot()
    assert "Ungültige Eingabe" in window.warning_label.text()
    window.axes_panel.x.min_edit.setText("0,5")
    assert window.replot()
    assert window.plot_view.figure.axes[0].get_xlim()[0] == 0.5


def test_editor_applies_to_all_selected(window, csv_file):
    window.add_files([csv_file])
    window.list_view.select_rows([0, 2])
    window.editor.draw.setCurrentIndex(window.editor.draw.findData("marker"))
    assert [d.draw for d in window.datasets] == ["marker", "line+marker", "marker"]
    assert not window.editor.label_edit.isEnabled()  # Legende nur bei einem Datensatz
    window.list_view.select_rows([1])
    window.editor.label_edit.setText("Mitte")
    assert window.datasets[1].label == "Mitte"


def test_visibility_toggle_from_list(window, csv_file):
    window.add_files([csv_file])
    window.model.toggle_visible(0)
    window.replot()
    assert "2 von 3" in window.status_label.text()


def test_statistics_y2_fit(window, csv_file):
    window.add_files([csv_file], statistics=True)
    window.add_files([csv_file])
    assert window.datasets[0].is_statistics
    window.axes_panel.y2_check.setChecked(True)
    window.datasets[1].axis = "Y2"
    window.datasets[0].fit = "linear"
    assert window.replot()
    assert len(window.plot_view.figure.axes) == 2
    legend = window.plot_view.figure.axes[1].get_legend()
    assert any(t.get_text().startswith("Fit:") for t in legend.get_texts())


def test_move_rows(window, csv_file):
    window.add_files([csv_file])
    first = window.datasets[0]
    window.list_view.select_rows([0])
    window.move_selected(1)
    assert window.datasets[1] is first
    assert window.list_view.selected_rows() == [1]


def test_presets(window, csv_file):
    window.add_files([csv_file])
    index = window.preset_combo.findData("paper1")
    window.preset_combo.setCurrentIndex(index)
    window._preset_chosen(index)
    settings = window.collect_settings()
    assert settings.label_fontsize == 9 and settings.export.width_cm == 8.5
    window.appearance.label_size.setValue(20)
    assert window.preset_combo.currentData() is None  # „Benutzerdefiniert“


def test_export_copy_and_project(window, csv_file, tmp_path, monkeypatch):
    window.add_files([csv_file])
    window.datasets[0].label = "Kanal A"
    window.appearance.title.setText("Versuch 1")
    window.axes_panel.y.prefix.setCurrentIndex(window.axes_panel.y.prefix.findData("m (milli)"))
    window.export_panel.width.setValue(12)

    target = str(tmp_path / "plot")
    monkeypatch.setattr(mw.QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: (target, mw.EXPORT_FILTERS[1][0])))  # SVG
    window.export()
    svg = (tmp_path / "plot.svg").read_text(encoding="utf-8")
    assert 'width="340.157' in svg  # 12 cm = 340,16 pt
    assert "Kanal A" in svg

    window.copy_plot()
    mime = QApplication.clipboard().mimeData()
    assert mime.hasImage() and mime.hasFormat("image/svg+xml")
    # Die Offscreen-Plattform der Tests stürzt beim Beenden mit gefüllter Zwischenablage ab
    # (die echte Windows-Plattform nicht) – daher leeren.
    QApplication.clipboard().clear()

    project = str(tmp_path / "proj.gplot")
    monkeypatch.setattr(mw.QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (project, "")))
    window.save_project()
    assert window.windowTitle().startswith("proj.gplot")

    window.datasets.clear()
    window.model.refresh()
    window.appearance.title.setText("")
    window.open_project(project)
    assert window.datasets[0].label == "Kanal A"
    assert window.appearance.title.text() == "Versuch 1"
    assert window.axes_panel.y.prefix.currentData() == "m (milli)"
    assert window.export_panel.width.value() == 12
    assert project.replace("/", "\\").lower() in [p.lower() for p in window._recent()]


def test_measurement(window, csv_file):
    window.add_files([csv_file])
    view = window.plot_view
    texts = []
    view.measured.connect(texts.append)
    view._set_mode("measure")
    ax = view.figure.axes[0]
    view.canvas.draw()
    for x, y in ((0, 1.0), (2, 3.0)):
        px, py = ax.transData.transform((x, y))
        view._on_click(SimpleNamespace(x=px, y=py, inaxes=ax, button=1))
    assert "Δx = 2" in texts[-1] and "Δy = 2" in texts[-1]
    view._set_mode("measure")  # ausschalten löscht die Messung
    assert texts[-1] == ""


def test_zoomed_view_export_copy_and_apply(window, tmp_path, monkeypatch):
    path = tmp_path / "lang.csv"
    path.write_text("t;U\n" + "\n".join(f"{i / 10};{(i % 7) / 3}".replace(".", ",") for i in range(41)),
                    encoding="utf-8")
    window.add_files([str(path)])
    assert not window.act_export_view.isEnabled()

    ax = window.plot_view.figure.axes[0]
    ax.set_xlim(1.0, 2.0)  # wie ein Zoom mit der Lupe
    assert window.plot_view.is_zoomed()
    assert window.act_export_view.isEnabled() and window.act_apply_view.isEnabled()

    captured = {}

    def fake_export(target, datasets, settings, options, fmt=None):
        captured["x"] = (settings.x.min, settings.x.max)
        captured["y"] = (settings.y.min, settings.y.max)
        Path(target).write_bytes(b"x")
        return SimpleNamespace(reductions=[])

    monkeypatch.setattr(mw, "export_plot", fake_export)
    monkeypatch.setattr(mw.QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: (str(tmp_path / "aus.pdf"), "")))
    window.export(view_only=True)
    assert captured["x"] == (1.0, 2.0)
    assert captured["y"] == ax.get_ylim()
    window.export()  # komplette Grafik: keine Grenzen
    assert captured["x"] == (None, None)

    window.copy_plot(view_only=True)
    assert QApplication.clipboard().mimeData().hasImage()
    QApplication.clipboard().clear()

    window.apply_view()
    assert window.axes_panel.x.min_edit.text() == "1"
    assert window.axes_panel.x.max_edit.text() == "2"
    assert window.plot_view.figure.axes[0].get_xlim() == (1.0, 2.0)
    assert not window.plot_view.is_zoomed()  # neue Ausgangsansicht


def test_combine_files_as_repeats(window, tmp_path):
    paths = []
    for i in range(3):
        path = tmp_path / f"lauf{i}.csv"
        path.write_text("t;U\n" + "\n".join(f"{t};{t + i}" for t in range(5)), encoding="utf-8")
        paths.append(str(path))
    window.add_files(paths)
    assert len(window.datasets) == 3
    window.list_view.select_rows([0, 1, 2])
    window._selection_changed()
    assert window.list_buttons["merge"].isEnabled()
    window.combine_selected()
    combined = window.datasets[3]
    assert combined.is_combined and combined.n_repeats == 3
    assert [d.visible for d in window.datasets] == [False, False, False, True]
    assert window.list_view.selected_rows() == [3]
    assert window._has_plot

    window.toggle_selected()
    assert not combined.visible


def test_run_busy_returns_result_and_raises(app):
    import time

    from graph_plotter.ui.tasks import run_busy

    def slow(value):
        time.sleep(0.6)  # länger als die Anzeigeschwelle: Fortschrittsfenster erscheint
        return value * 2

    assert run_busy(None, "Test", slow, 21) == 42
    with pytest.raises(ZeroDivisionError):
        run_busy(None, "Test", lambda: 1 / 0)


def test_progress_dialog_does_not_reappear(app):
    """Regression: „Bitte warten“ tauchte ~4 s nach dem Laden über dem Importdialog wieder auf.

    Ursache war der interne 4-s-Zeitgeber von QProgressDialog; aufgedeckt wird das nur, wenn das Laden
    aus der laufenden Ereignisschleife kommt (wie ein Klick) und danach eine verschachtelte Schleife
    (Importdialog) offen bleibt.
    """
    import time

    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QProgressDialog

    from graph_plotter.ui.tasks import run_busy

    seen = []

    def visible_progress():
        return [w for w in QApplication.topLevelWidgets() if isinstance(w, QProgressDialog) and w.isVisible()]

    def scenario():
        run_busy(None, "kurz", time.sleep, 0.1)        # Fenster wird gar nicht erst nötig
        run_busy(None, "lang", time.sleep, 0.6)        # Fenster erscheint kurz
        nested = QEventLoop()                          # wie der offene Importdialog
        for delay in (1000, 4700):
            QTimer.singleShot(delay, lambda: seen.append(len(visible_progress())))
        QTimer.singleShot(4800, nested.quit)
        nested.exec()
        outer.quit()

    outer = QEventLoop()
    QTimer.singleShot(0, scenario)
    outer.exec()
    assert seen == [0, 0]


def _release(version=(9, 1), setup=True):
    from graph_plotter.updates import ReleaseInfo
    return ReleaseInfo(version=version, tag="v" + ".".join(map(str, version)),
                       page_url="https://example.invalid/release",
                       setup_url="https://example.invalid/setup.exe" if setup else "", setup_name="setup.exe")


def test_update_banner_and_skip(window, monkeypatch):
    from graph_plotter.ui import update_ui
    opened = []
    monkeypatch.setattr(update_ui.QDesktopServices, "openUrl", staticmethod(lambda url: opened.append(url.toString())))
    infos = []
    monkeypatch.setattr(update_ui.QMessageBox, "information", staticmethod(lambda *a, **k: infos.append(a[2])))

    controller = window.updates
    controller._found(_release((0, 1)), True)            # ältere Version, manuell gesucht
    assert not window.update_banner.isVisibleTo(window) and "neueste Version" in infos[-1]

    controller._found(_release(), False)                 # neuere Version beim Start
    assert window.update_banner.isVisibleTo(window)
    assert "9.1 ist verfügbar" in window.update_banner.label.text()
    assert window.update_banner.update_button.text() == "Herunterladen"   # aus Python gestartet

    window.update_banner.update_button.click()           # nicht installiert: Download-Seite öffnen
    assert opened == ["https://example.invalid/release"]

    window.update_banner.skip_button.click()
    assert window.store.value("update_skip_tag") == "v9.1"
    assert not window.update_banner.isVisibleTo(window)
    controller._found(_release(), False)                 # übersprungene Version: kein Hinweis
    assert not window.update_banner.isVisibleTo(window)
    controller._found(_release(), True)                  # bei manueller Suche aber schon
    assert window.update_banner.isVisibleTo(window)


def test_update_install_flow(window, monkeypatch, tmp_path):
    """Installierte Fassung: herunterladen, Installer starten, Programm beenden."""
    from graph_plotter import app as app_module
    from graph_plotter.ui import update_ui

    setup = tmp_path / "setup.exe"
    setup.write_bytes(b"x")
    calls = []
    monkeypatch.setattr(update_ui.updates, "install_kind", lambda: "installed")
    monkeypatch.setattr(update_ui.updates, "download",
                        lambda info, progress=None, cancelled=None: (progress(1, 1), setup)[1])
    monkeypatch.setattr(update_ui.updates, "launch_installer", lambda path: calls.append(("start", path)))
    monkeypatch.setattr(app_module, "release_mutex", lambda: calls.append(("mutex",)))
    monkeypatch.setattr(update_ui.QApplication, "quit", staticmethod(lambda: calls.append(("quit",))))
    monkeypatch.setattr(update_ui.UpdateController, "_confirm", lambda self, info: True)

    window.updates._found(_release(), False)
    assert window.update_banner.update_button.text() == "Jetzt aktualisieren"
    window.update_banner.update_button.click()
    for _ in range(100):                                  # Download läuft im Hintergrund
        QApplication.processEvents()
        if calls:
            break
        import time
        time.sleep(0.02)
    assert calls == [("mutex",), ("start", setup), ("quit",)]


def test_selftest_passes(app):
    from graph_plotter.selftest import run_selftest
    assert run_selftest() == 0


def test_page_mode_and_theme(window, csv_file):
    window.add_files([csv_file])
    window.plot_view.set_page_mode(True)
    assert window.plot_view.canvas.width() == round(16 / 2.54 * 100)
    window.plot_view.set_page_mode(False)
    window.set_theme("dark")
    assert window.store.value("theme") == "dark"
    window.set_theme("light")


def test_import_dialog(app, tmp_path):
    path = tmp_path / "d.csv"
    path.write_text("Kommentar\nx,a,b\n1,2,3\n2,3,4\n", encoding="utf-8")
    table = read_table(str(path))
    dialog = ImportDialog(None, str(path), table, default_spec(str(path), table))
    spec = dialog.spec()
    assert (spec.header_row, spec.data_start, spec.y_cols) == (1, 2, [1, 2])
    dialog.x_combo.setCurrentIndex(1)
    assert dialog.spec().y_cols == [0, 2]
    dialog.header_spin.setValue(0)
    assert dialog.spec().header_row is None
