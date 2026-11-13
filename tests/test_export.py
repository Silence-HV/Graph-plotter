import re

import numpy as np
import pytest
from matplotlib.figure import Figure

from graph_plotter.exporting import ExportOptions, export_plot
from graph_plotter.model import Dataset
from graph_plotter.plotting import PlotSettings, render
from graph_plotter.reduction import (Reduction, band_reduce, dedupe_markers, minmax_reduce,
                                     thinning_step)


# --------------------------------------------------------------------------- reduction

def test_minmax_keeps_extremes_and_order():
    rng = np.random.default_rng(0)
    x = np.linspace(0, 1, 100_000)
    y = rng.standard_normal(len(x))
    y[12_345] = 50.0   # Ausreißer
    y[67_890] = -50.0
    rx, ry = minmax_reduce(x, y, 1000)
    assert len(rx) <= 4 * 1000
    assert ry.max() == 50.0 and ry.min() == -50.0
    assert np.all(np.diff(rx) >= 0)
    assert rx[0] == x[0] and rx[-1] == x[-1]


def test_minmax_preserves_per_column_envelope():
    rng = np.random.default_rng(1)
    x = np.sort(rng.uniform(0, 10, 50_000))
    y = np.sin(x) + rng.standard_normal(len(x))
    n_bins = 500
    rx, ry = minmax_reduce(x, y, n_bins)
    bins = np.minimum(((x - x[0]) / (x[-1] - x[0]) * n_bins).astype(int), n_bins - 1)
    rbins = np.minimum(((rx - x[0]) / (x[-1] - x[0]) * n_bins).astype(int), n_bins - 1)
    for b in (0, 123, 499):
        assert ry[rbins == b].max() == y[bins == b].max()
        assert ry[rbins == b].min() == y[bins == b].min()


def test_minmax_leaves_small_or_unsorted_data_alone():
    x = np.arange(100.0)
    assert len(minmax_reduce(x, x, 1000)[0]) == 100
    unsorted = np.array([3.0, 1.0, 2.0] * 10_000)
    assert len(minmax_reduce(unsorted, unsorted, 10)[0]) == len(unsorted)


def test_minmax_log_axis():
    x = np.logspace(0, 6, 100_000)
    rx, _ = minmax_reduce(x, np.ones_like(x), 100, log=True)
    # Logarithmisch gleichmäßige Intervalle: auch die erste Dekade bleibt aufgelöst
    assert np.sum(rx < 10) >= 10


def test_band_reduce_envelope():
    x = np.linspace(0, 1, 10_000)
    lo = -np.ones_like(x)
    hi = np.ones_like(x)
    lo[5000] = -9
    hi[42] = 9
    bx, blo, bhi = band_reduce(x, lo, hi, 100)
    assert len(bx) <= 200 and blo.min() == -9 and bhi.max() == 9


def test_dedupe_markers():
    x = np.repeat(np.arange(10.0), 1000)
    y = np.tile(np.linspace(0, 1e-6, 1000), 10)  # je X fast gleiche Y-Werte
    idx = dedupe_markers(x, y, (0, 9), (0, 1), 100, 100, cell_px=1)
    assert len(idx) == 10


def test_thinning_step():
    assert thinning_step(100, 250) == 1
    assert thinning_step(1000, 250) == 4


# --------------------------------------------------------------------------- render/export

def big_datasets(draw="line+marker", n=200_000):
    x = np.linspace(0, 10, n)
    rng = np.random.default_rng(2)
    return [Dataset(name=f"K{k}", x=x, y=np.sin(x * (k + 1)) + 0.05 * rng.standard_normal(n), draw=draw)
            for k in range(3)]


def test_render_with_reduction_reports():
    reduction = Reduction(width_px=1900, height_px=1200, dpi=300)
    result = render(Figure(), big_datasets(), PlotSettings(), reduction=reduction)
    assert len(result.reductions) == 3
    assert "Marker an jedem 800. Punkt" in result.reductions[0]


def test_screen_render_is_not_reduced():
    fig = Figure()
    render(fig, big_datasets(n=50_000), PlotSettings())
    assert len(fig.axes[0].get_lines()[0].get_xdata()) == 50_000


@pytest.mark.parametrize("draw", ["line+marker", "marker", "line"])
def test_svg_export_stays_small(tmp_path, draw):
    path = tmp_path / "plot.svg"
    options = ExportOptions(width_in=16 / 2.54, height_in=10 / 2.54, dpi=300)
    settings = PlotSettings(label_fontsize=11, tick_fontsize=9, legend_fontsize=9)
    export_plot(str(path), big_datasets(draw), settings, options)
    text = path.read_text(encoding="utf-8")
    size_mb = path.stat().st_size / 1e6
    assert size_mb < 3, f"{draw}: {size_mb:.1f} MB"
    assert text.count("<use ") < 30_000
    # Text bleibt bearbeitbar (echte <text>-Elemente in Arial)
    assert "<text" in text and "Arial" in text


def test_statistics_errorbars_thinned(tmp_path):
    n = 100_000
    x = np.linspace(0, 1, n)
    y_raw = np.vstack([np.sin(x) + 0.1 * k for k in range(3)])
    ds = Dataset(name="S", x=x, y_raw=y_raw, draw="line+marker")
    path = tmp_path / "s.pdf"
    result = export_plot(str(path), [ds], PlotSettings(),
                         ExportOptions(width_in=6, height_in=4, dpi=300))
    assert any("Fehlerbalken an jedem" in r for r in result.reductions)
    assert path.stat().st_size < 1_000_000


def test_text_as_paths_option(tmp_path):
    path = tmp_path / "p.svg"
    ds = Dataset(name="A", x=np.arange(10.0), y=np.arange(10.0))
    export_plot(str(path), [ds], PlotSettings(),
                ExportOptions(width_in=4, height_in=3, editable_text=False))
    assert "<text" not in path.read_text(encoding="utf-8")


@pytest.mark.parametrize("ext", ["png", "pdf", "eps", "jpg", "tiff", "webp", "svgz"])
def test_all_formats(tmp_path, ext):
    path = tmp_path / f"p.{ext}"
    ds = Dataset(name="A", x=np.arange(10.0), y=np.arange(10.0))
    export_plot(str(path), [ds], PlotSettings(), ExportOptions(width_in=4, height_in=3, dpi=100))
    assert path.stat().st_size > 0


def test_pdf_embeds_truetype(tmp_path):
    path = tmp_path / "p.pdf"
    ds = Dataset(name="A", x=np.arange(10.0), y=np.arange(10.0))
    export_plot(str(path), [ds], PlotSettings(), ExportOptions(width_in=4, height_in=3))
    data = path.read_bytes()
    # pdf.fonttype 42: TrueType wird als CIDFontType2 eingebettet statt als Type-3-Zeichenprozedur
    assert b"CIDFontType2" in data and b"/Type3" not in data
    assert re.search(rb"/BaseFont\s*/\w+\+Arial", data)
