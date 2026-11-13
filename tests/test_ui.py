"""Rauchtests der Oberfläche (ohne sichtbares Fenster)."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt5")

import matplotlib  # noqa: E402

matplotlib.use("Qt5Agg")

from PyQt5.QtWidgets import QApplication, QDialog  # noqa: E402

from graph_plotter.loaders import default_spec, read_table  # noqa: E402
from graph_plotter.ui import main_window as mw  # noqa: E402
from graph_plotter.ui.dialogs import ImportDialog  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app, monkeypatch):
    # Dialoge nicht blockieren lassen
    for name in ("warning", "information", "critical"):
        monkeypatch.setattr(mw.QMessageBox, name, staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(mw.QMessageBox, "question", staticmethod(lambda *a, **k: mw.QMessageBox.Yes))
    win = mw.MainWindow()
    win.import_dialog_check.setChecked(False)
    yield win
    win.close()


@pytest.fixture
def csv_file(tmp_path):
    path = tmp_path / "messung.csv"
    path.write_text("Zeit;U1;U2;U3\n0;1,0;1,2;0,9\n1;2,0;2,1;1,9\n2;3,0;3,3;2,8\n", encoding="utf-8")
    return str(path)


def test_load_plot_remove(window, csv_file):
    window.add_files([csv_file])
    assert len(window.datasets) == 3
    assert window._has_plot
    assert len({d.color for d in window.datasets}) == 3

    # eigene Labels/Farben bleiben beim Entfernen am richtigen Datensatz (F4/F5)
    window.datasets[2].label = "Dritte"
    window.datasets[2].color = "#000000"
    window.table.selectRow(0)
    window.remove_selected()
    assert [d.display_label for d in window.datasets][-1] == "Dritte"
    assert window.datasets[-1].color == "#000000"
    assert window.table.rowCount() == 2


def test_invalid_input_blocks_plot(window, csv_file):
    window.add_files([csv_file])
    window.x_box.min_edit.setText("abc")
    assert not window.plot(silent=True)
    window.x_box.min_edit.setText("0,5")
    assert window.plot(silent=True)
    assert window.fig.axes[0].get_xlim()[0] == 0.5


def test_statistics_y2_and_fit(window, csv_file):
    window.stat_default_check.setChecked(True)
    window.add_files([csv_file])
    window.stat_default_check.setChecked(False)
    window.add_files([csv_file])
    window.y2_check.setChecked(True)
    window.datasets[1].axis = "Y2"
    window.datasets[0].fit = "linear"
    assert window.plot(silent=True)
    assert len(window.fig.axes) == 2


def test_move_rows(window, csv_file):
    window.add_files([csv_file])
    first = window.datasets[0]
    window.table.selectRow(0)
    window.move_selected(1)
    assert window.datasets[1] is first
    assert window._selected_rows() == [1]


def test_export_and_project(window, csv_file, tmp_path, monkeypatch):
    window.add_files([csv_file])
    window.datasets[0].label = "Kanal A"
    window.title_edit.setText("Versuch 1")
    window.y_box.prefix.setCurrentIndex(window.y_box.prefix.findData("m (milli)"))

    target = str(tmp_path / "plot")
    monkeypatch.setattr(mw.QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: (target, mw.EXPORT_FORMATS[1][0])))
    monkeypatch.setattr(mw.ExportDialog, "exec_", lambda self: QDialog.Accepted)
    window.export_plot()
    assert (tmp_path / "plot.pdf").stat().st_size > 0

    project = str(tmp_path / "proj.gplot")
    monkeypatch.setattr(mw.QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (project, "")))
    window.save_project()
    window.datasets.clear()
    window.title_edit.setText("")
    window.open_project(project)
    assert window.datasets[0].label == "Kanal A"
    assert window.title_edit.text() == "Versuch 1"
    assert window.y_box.prefix.currentData() == "m (milli)"


def test_import_dialog(app, tmp_path):
    path = tmp_path / "d.csv"
    path.write_text("Kommentar\nx,a,b\n1,2,3\n2,3,4\n", encoding="utf-8")
    table = read_table(str(path))
    dialog = ImportDialog(None, str(path), table, default_spec(str(path), table))
    spec = dialog.spec()
    assert (spec.header_row, spec.data_start, spec.y_cols) == (1, 2, [1, 2])
    # X-Spalte wechseln: die X-Spalte wird aus der Y-Auswahl ausgeblendet
    dialog.x_combo.setCurrentIndex(1)
    assert dialog.spec().y_cols == [0, 2]
    dialog.header_spin.setValue(0)
    assert dialog.spec().header_row is None
