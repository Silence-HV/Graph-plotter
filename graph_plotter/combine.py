"""Mehrere Datensätze (z. B. eine Datei je Messung) zu Messwiederholungen zusammenfassen."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .model import Dataset


@dataclass
class CombineResult:
    dataset: Dataset
    interpolated: bool
    note: str = ""


def _series(datasets: list[Dataset]) -> list[tuple[np.ndarray, np.ndarray, str]]:
    """Alle Einzelreihen (Statistik-Datensätze liefern jede Wiederholung einzeln), nach X sortiert."""
    result = []
    for ds in datasets:
        rows = list(ds.y_raw) if ds.is_statistics else [ds.y]
        for y in rows:
            x = np.asarray(ds.x, dtype=float)
            y = np.asarray(y, dtype=float)
            mask = np.isfinite(x) & np.isfinite(y)
            order = np.argsort(x[mask], kind="stable")
            result.append((x[mask][order], y[mask][order], ds.display_label))
    return result


def combine_repeats(datasets: list[Dataset], name: str | None = None) -> CombineResult:
    """Datensätze als Messwiederholungen zu einem Statistik-Datensatz zusammenfassen.

    Haben alle Reihen dieselben X-Werte, werden sie direkt übereinandergelegt. Sonst werden sie auf
    die X-Werte der ersten Reihe linear interpoliert; außerhalb ihres Messbereichs zählt eine Reihe
    an dieser Stelle nicht mit.

    Raises:
        ValueError: bei weniger als zwei Reihen oder ohne gemeinsamen Bereich.
    """
    series = _series(datasets)
    if len(series) < 2:
        raise ValueError("Zum Zusammenfassen mindestens zwei Messreihen auswählen.")
    grid = series[0][0]
    if len(grid) == 0:
        raise ValueError(f"„{series[0][2]}“ enthält keine gültigen Werte.")

    identical = all(len(x) == len(grid) and np.allclose(x, grid, rtol=1e-9, atol=1e-12) for x, _, _ in series)
    rows = []
    for x, y, _ in series:
        if identical:
            rows.append(y)
        elif len(x) == 0:
            rows.append(np.full(len(grid), np.nan))
        else:
            rows.append(np.interp(grid, x, y, left=np.nan, right=np.nan))
    y_raw = np.vstack(rows)
    if not np.isfinite(y_raw).sum(axis=0).max() >= 2:
        raise ValueError("Die Messreihen haben keinen gemeinsamen X-Bereich.")

    members = [ds.spec for ds in datasets if ds.spec is not None]
    members += [m for ds in datasets for m in ds.members]
    combined = Dataset(
        name=name or f"Mittelwert aus {len(series)} Messungen",
        x=grid.copy(), y_raw=y_raw, members=members,
        linestyle="--", linewidth=1.8, markersize=6, marker_filled=False,
    )
    note = "" if identical else (f"Die X-Werte der Messreihen unterscheiden sich: Alle Reihen wurden auf die "
                                 f"X-Werte von „{series[0][2]}“ interpoliert.")
    return CombineResult(combined, not identical, note)
