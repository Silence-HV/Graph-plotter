"""Statistik über Messwiederholungen: Mittelwert und Fehlermaß."""

from __future__ import annotations

import warnings

import numpy as np

ERROR_MODES = {
    "sd": "SD",          # Stichproben-Standardabweichung (ddof=1)
    "sem": "SEM",        # Standardfehler des Mittelwerts
    "ci95": "95 %-KI",   # 95-%-Konfidenzintervall (t-Verteilung)
}

ERROR_MODE_NAMES = {
    "sd": "Standardabweichung (SD)",
    "sem": "Standardfehler (SEM)",
    "ci95": "95 %-Konfidenzintervall",
}

# Zweiseitige 95-%-Quantile der t-Verteilung für Freiheitsgrade 1..30
_T95 = [12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262, 2.228,
        2.201, 2.179, 2.160, 2.145, 2.131, 2.120, 2.110, 2.101, 2.093, 2.086,
        2.080, 2.074, 2.069, 2.064, 2.060, 2.056, 2.052, 2.048, 2.045, 2.042]


def t95(df: int) -> float:
    """t-Quantil für ein zweiseitiges 95-%-Intervall (für große df konservativ gerundet)."""
    if df < 1:
        return float("nan")
    if df <= 30:
        return _T95[df - 1]
    if df < 40:
        return 2.042
    if df < 60:
        return 2.021
    if df < 120:
        return 2.000
    return 1.980


def summarize(y_raw, mode: str = "sd") -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Mittelwert, Fehlermaß und Anzahl gültiger Werte je Messpunkt.

    Args:
        y_raw: Array der Form (Messungen, Punkte); NaN = fehlender Wert.
        mode: "sd", "sem" oder "ci95".

    Returns:
        (mean, err, n). Bei weniger als zwei gültigen Werten ist err NaN,
        ohne gültige Werte auch mean.
    """
    if mode not in ERROR_MODES:
        raise ValueError(f"Unbekanntes Fehlermaß: {mode}")
    y = np.asarray(y_raw, dtype=float)
    if y.ndim == 1:
        y = y[np.newaxis, :]
    n = np.sum(np.isfinite(y), axis=0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        mean = np.nanmean(y, axis=0)
        sd = np.nanstd(y, axis=0, ddof=1)
    sd = np.where(n >= 2, sd, np.nan)

    if mode == "sd":
        err = sd
    else:
        with np.errstate(invalid="ignore", divide="ignore"):
            sem = sd / np.sqrt(n)
        if mode == "sem":
            err = sem
        else:
            t = np.array([t95(int(k) - 1) for k in n], dtype=float)
            err = t * sem
    return mean, err, n
