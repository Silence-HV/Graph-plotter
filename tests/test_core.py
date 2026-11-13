import datetime as dt

import numpy as np
import pytest
from matplotlib.figure import Figure

from graph_plotter.fitting import fit_curve
from graph_plotter.loaders import (LoadError, default_spec, detect_delimiter, detect_layout,
                                   load_datasets, read_table)
from graph_plotter.model import Dataset, ImportSpec
from graph_plotter.numparse import parse_number, parse_optional
from graph_plotter.plotting import AxisSettings, PlotError, PlotSettings, axis_label, render
from graph_plotter.project import load_project, save_project
from graph_plotter.stats import summarize, t95


# --------------------------------------------------------------------------- numparse

@pytest.mark.parametrize("text, expected", [
    ("3,14", 3.14),
    ("3.14", 3.14),
    ("-0,5", -0.5),
    ("1.000,5", 1000.5),
    ("1,000.5", 1000.5),
    ("1 000,5", 1000.5),
    ("1,5E+9", 1.5e9),
    ("2,3e-6", 2.3e-6),
    ("1.234.567", 1234567.0),
    ("−2,5", -2.5),
    (7, 7.0),
    (2.5, 2.5),
])
def test_parse_number(text, expected):
    assert parse_number(text) == pytest.approx(expected)


@pytest.mark.parametrize("text", [None, "", "  ", "abc", "Messwert", "1,2,3x", True])
def test_parse_number_invalid(text):
    with pytest.raises(ValueError):
        parse_number(text)


def test_parse_optional():
    assert parse_optional("") is None
    assert parse_optional("0,5") == 0.5
    with pytest.raises(ValueError):
        parse_optional("x")
    with pytest.raises(ValueError):
        parse_optional("inf")


# --------------------------------------------------------------------------- loaders

def write(tmp_path, name, text, encoding="utf-8"):
    path = tmp_path / name
    path.write_bytes(text.encode(encoding))
    return str(path)


def test_detect_delimiter():
    assert detect_delimiter("a;b\n1,5;2\n") == ";"
    assert detect_delimiter("a\tb\n1\t2\n") == "\t"
    assert detect_delimiter("a,b\n1,2\n") == ","


def test_csv_english(tmp_path):
    path = write(tmp_path, "m.csv", "t,U,I\n0,1.5,2\n1,2.5,3\n2,3.5,\n")
    result = load_datasets(default_spec(path))
    assert [d.source_column for d in result.datasets] == ["U", "I"]
    assert result.datasets[0].y.tolist() == [1.5, 2.5, 3.5]
    assert result.datasets[1].x.tolist() == [0, 1]  # fehlender Wert entfernt


def test_csv_german_cp1252(tmp_path):
    text = "Gerät: Oszi\nZeit [s];Spannung µV\n0,0;1,5E-3\n0,1;2,5E-3\n"
    path = write(tmp_path, "de.csv", text, encoding="cp1252")
    table = read_table(path)
    assert detect_layout(table.rows) == (1, 2)
    result = load_datasets(default_spec(path, table), table)
    ds = result.datasets[0]
    assert ds.source_column == "Spannung µV"
    assert ds.x.tolist() == pytest.approx([0.0, 0.1])
    assert ds.y.tolist() == pytest.approx([1.5e-3, 2.5e-3])


def test_csv_without_header_keeps_first_row(tmp_path):
    path = write(tmp_path, "nohead.csv", "0,1\n1,2\n2,3\n")
    spec = default_spec(path)
    assert spec.header_row is None
    ds = load_datasets(spec).datasets[0]
    assert ds.n_points == 3


def test_skipped_rows_and_sort(tmp_path):
    path = write(tmp_path, "s.csv", "x,y\n2,20\n3,30\nkaputt,1\n1,10\n\n\n")
    spec = default_spec(path)
    spec.sort_x = True
    result = load_datasets(spec)
    assert result.skipped_rows == 1
    assert result.datasets[0].x.tolist() == [1, 2, 3]
    assert result.datasets[0].y.tolist() == [10, 20, 30]


def test_statistics_dataset(tmp_path):
    path = write(tmp_path, "st.csv", "x,a,b,c\n0,1,2,3\n1,,,\n2,5,,\n")
    spec = default_spec(path, statistics=True)
    ds = load_datasets(spec).datasets[0]
    assert ds.is_statistics and ds.n_repeats == 3
    assert ds.spec.y_cols == [1, 2, 3]


def test_xlsx_with_sheet_and_dates(tmp_path):
    from openpyxl import Workbook

    wb = Workbook()
    wb.active.title = "Leer"
    ws = wb.create_sheet("Messung")
    ws.append(["Zeit", "Temp"])
    start = dt.datetime(2026, 1, 1, 12, 0, 0)
    for i in range(3):
        ws.append([start + dt.timedelta(seconds=10 * i), "20,5" if i == 0 else 21 + i])
    path = str(tmp_path / "t.xlsx")
    wb.save(path)

    table = read_table(path, "Messung")
    assert table.sheets == ["Leer", "Messung"]
    result = load_datasets(default_spec(path, table), table)
    assert result.x_is_time
    ds = result.datasets[0]
    assert ds.x.tolist() == [0, 10, 20]
    assert ds.y.tolist() == [20.5, 22, 23]
    with pytest.raises(LoadError):
        read_table(path, "Gibtsnicht")


def test_missing_file():
    with pytest.raises(LoadError):
        read_table("gibt_es_nicht.csv")


# --------------------------------------------------------------------------- stats / fit

def test_summarize_modes():
    y = np.array([[1.0, 1.0, np.nan], [3.0, np.nan, np.nan]])
    mean, sd, n = summarize(y, "sd")
    assert mean[0] == 2.0 and n.tolist() == [2, 1, 0]
    assert sd[0] == pytest.approx(np.sqrt(2))  # ddof=1
    assert np.isnan(sd[1]) and np.isnan(mean[2])
    _, sem, _ = summarize(y, "sem")
    assert sem[0] == pytest.approx(1.0)
    _, ci, _ = summarize(y, "ci95")
    assert ci[0] == pytest.approx(12.706)
    assert t95(100) == pytest.approx(2.0)


def test_fit_linear_and_exp():
    x = np.linspace(0, 10, 20)
    lin = fit_curve(x, 2 * x + 1, "linear")
    assert lin.coefficients == pytest.approx([1, 2])
    assert lin.r2 == pytest.approx(1.0)
    assert lin.equation == "y = 2·x + 1"
    ex = fit_curve(x, 3 * np.exp(-0.5 * x), "exp")
    assert ex.coefficients == pytest.approx([3, -0.5])
    with pytest.raises(ValueError):
        fit_curve(x, -x - 1, "exp")
    with pytest.raises(ValueError):
        fit_curve([1, 2], [1, 2], "poly3")


def test_fit_large_x_offsets():
    x = 1.7e9 + np.arange(10.0)
    fit = fit_curve(x, 0.5 * (x - 1.7e9) + 4, "linear")
    assert fit.r2 == pytest.approx(1.0)


# --------------------------------------------------------------------------- plotting

def make(name, x, y, **kw):
    return Dataset(name=name, x=np.asarray(x, float), y=np.asarray(y, float), **kw)


def test_axis_label_prefix():
    assert axis_label(AxisSettings(label="U", unit="V", prefix="m (milli)"), "Wert") == "U [mV]"
    assert axis_label(AxisSettings(prefix="k (kilo)"), "Wert") == "Wert [$\\times 10^{3}$]"
    assert axis_label(AxisSettings(), "Zeit") == "Zeit"


def test_render_y2_autoscale_is_separate():
    d1 = make("a", [0, 1, 2], [0.001, 0.002, 0.003])
    d2 = make("b", [0, 1, 2], [1000, 2000, 3000], axis="Y2")
    settings = PlotSettings(y2_enabled=True)
    result = render(Figure(), [d1, d2], settings)
    assert result.limits["y"][1] < 1
    assert result.limits["y2"][1] > 2000


def test_render_statistics_with_nan_rows():
    ds = Dataset(name="s", x=np.array([0.0, 1.0, 2.0]),
                 y_raw=np.array([[1.0, np.nan, 3.0], [2.0, np.nan, 4.0]]))
    result = render(Figure(), [ds], PlotSettings())
    assert all(np.isfinite(result.limits["y"]))


def test_render_scaling_limits_and_ticks():
    ds = make("a", [0, 0.001, 0.002], [0, 1, 2])
    settings = PlotSettings(x=AxisSettings(prefix="m (milli)", min=0.5, tick=1e-6))
    result = render(Figure(), [ds], settings)
    assert result.limits["x"][0] == 0.5
    assert any("Markierungen" in w for w in result.warnings)


def test_render_errors():
    with pytest.raises(PlotError):
        render(Figure(), [], PlotSettings())
    hidden = make("a", [0, 1], [0, 1], visible=False)
    with pytest.raises(PlotError):
        render(Figure(), [hidden], PlotSettings())
    ds = make("a", [0, 1], [0, 1])
    with pytest.raises(PlotError):
        render(Figure(), [ds], PlotSettings(x=AxisSettings(min=5)))


def test_render_fit_log_and_invalid_limits():
    ds = make("a", [1, 2, 3, 4], [2, 4, 8, 16], fit="exp")
    settings = PlotSettings(y=AxisSettings(log=True, min=-1), legend_loc="outside", minor_ticks=True)
    result = render(Figure(), [ds], settings)
    assert any("logarithmischer" in w for w in result.warnings)
    fig = Figure()
    render(fig, [ds], settings)
    legend_texts = [t.get_text() for t in fig.axes[0].get_legend().get_texts()]
    assert any(t.startswith("Fit: y = 1·e^(0.6931·x)") for t in legend_texts)


# --------------------------------------------------------------------------- project

def test_project_roundtrip(tmp_path):
    data_dir = tmp_path / "daten"
    data_dir.mkdir()
    path = write(data_dir, "m.csv", "t;a;b\n0;1;2\n1;2;3\n")
    datasets = load_datasets(default_spec(path)).datasets
    datasets[1].label = "Eigener Name"
    datasets[1].color = "#123456"
    datasets[1].axis = "Y2"
    settings = PlotSettings(title="Test", y2_enabled=True, x=AxisSettings(unit="s", min=0.5))
    project_file = tmp_path / "p.gplot"
    save_project(str(project_file), datasets, settings)

    # Projekt samt Daten verschieben: relativer Pfad muss greifen
    moved = tmp_path / "neu"
    moved.mkdir()
    (moved / "daten").mkdir()
    (data_dir / "m.csv").rename(moved / "daten" / "m.csv")
    project_file.rename(moved / "p.gplot")

    loaded = load_project(str(moved / "p.gplot"))
    assert loaded.problems == []
    assert [d.display_label for d in loaded.datasets] == ["m – a", "Eigener Name"]
    assert loaded.datasets[1].color == "#123456" and loaded.datasets[1].axis == "Y2"
    assert loaded.settings.title == "Test" and loaded.settings.x.min == 0.5


def test_project_missing_file(tmp_path):
    path = write(tmp_path, "m.csv", "t,a\n0,1\n1,2\n")
    datasets = load_datasets(default_spec(path)).datasets
    project_file = str(tmp_path / "p.gplot")
    save_project(project_file, datasets, PlotSettings())
    (tmp_path / "m.csv").unlink()
    loaded = load_project(project_file)
    assert loaded.datasets == [] and len(loaded.problems) == 1


def test_import_spec_from_dict_ignores_unknown():
    spec = ImportSpec.from_dict({"path": "a.csv", "x_col": 1, "unbekannt": 5})
    assert spec.x_col == 1
