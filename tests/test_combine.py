import numpy as np
import pytest

from graph_plotter.combine import combine_repeats
from graph_plotter.loaders import default_spec, load_datasets
from graph_plotter.model import Dataset
from graph_plotter.plotting import PlotSettings
from graph_plotter.project import load_project, save_project
from graph_plotter.stats import summarize


def ds(name, x, y):
    return Dataset(name=name, x=np.asarray(x, float), y=np.asarray(y, float))


def test_identical_x_is_stacked():
    result = combine_repeats([ds("a", [0, 1, 2], [1, 2, 3]), ds("b", [0, 1, 2], [3, 4, 5])])
    assert not result.interpolated and result.note == ""
    mean, sd, n = summarize(result.dataset.y_raw, "sd")
    assert mean.tolist() == [2, 3, 4] and n.tolist() == [2, 2, 2]
    assert result.dataset.name == "Mittelwert aus 2 Messungen"


def test_different_x_is_interpolated_on_first_grid():
    a = ds("a", [0, 1, 2, 3], [0, 10, 20, 30])
    b = ds("b", [0.5, 1.5, 2.5], [5, 15, 25])  # gleiche Gerade, anderes Raster, kürzer
    result = combine_repeats([a, b])
    assert result.interpolated and "interpoliert" in result.note
    y = result.dataset.y_raw
    assert np.isnan(y[1, 0]) and np.isnan(y[1, 3])      # außerhalb des Bereichs von b
    assert y[1, 1:3].tolist() == pytest.approx([10, 20])


def test_unsorted_input_and_statistics_members():
    a = ds("a", [2, 0, 1], [3, 1, 2])
    stat = Dataset(name="s", x=np.array([0.0, 1.0, 2.0]), y_raw=np.array([[1.0, 2.0, 3.0], [2.0, 3.0, 4.0]]))
    result = combine_repeats([a, stat])
    assert result.dataset.y_raw.shape == (3, 3)
    assert result.dataset.x.tolist() == [0, 1, 2]


def test_errors():
    with pytest.raises(ValueError):
        combine_repeats([ds("a", [0, 1], [1, 2])])
    with pytest.raises(ValueError):
        combine_repeats([ds("a", [0, 1], [1, 2]), ds("b", [5, 6], [1, 2])])


def test_project_roundtrip_with_combined(tmp_path):
    paths = []
    for i in range(3):
        path = tmp_path / f"messung{i}.csv"
        path.write_text("t;U\n" + "\n".join(f"{t};{t * 2 + i}" for t in range(5)), encoding="utf-8")
        paths.append(str(path))
    singles = [load_datasets(default_spec(p)).datasets[0] for p in paths]
    combined = combine_repeats(singles).dataset
    combined.label = "Mittel"
    project = str(tmp_path / "p.gplot")
    save_project(project, singles + [combined], PlotSettings())

    loaded = load_project(project)
    assert loaded.problems == []
    restored = loaded.datasets[-1]
    assert restored.is_combined and restored.display_label == "Mittel"
    assert np.array_equal(restored.y_raw, combined.y_raw)
