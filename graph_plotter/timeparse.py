"""Datum und Uhrzeit aus Text erkennen (z. B. Zeitstempel von Datenloggern in CSV-Dateien)."""

from __future__ import annotations

import re
from typing import Optional

import numpy as np
import pandas as pd

_DATE_RE = re.compile(r"^\d{1,4}[-./]\d{1,2}[-./]\d{1,4}(?:[ T]+\d{1,2}:\d{2}(?::\d{2}(?:[.,]\d+)?)?)?$")
_TIME_RE = re.compile(r"^\d{1,2}:\d{2}(?::\d{2}(?:[.,]\d+)?)?$")


def _with_time(date: str) -> tuple[str, ...]:
    """Datumsformat mit Uhrzeit in absteigender Genauigkeit (ergänzen sich bei gemischten Werten)."""
    return (f"{date} %H:%M:%S.%f", f"{date} %H:%M:%S", f"{date} %H:%M", date)


# (Formate einer Gruppe, nur Uhrzeit). Formate einer Gruppe ergänzen sich: Werte mit und ohne
# Sekundenbruchteile dürfen gemischt sein. Reihenfolge = Vorrang bei Mehrdeutigkeit (deutsch vor US).
FORMAT_GROUPS: list[tuple[tuple[str, ...], bool]] = [
    (("ISO8601",), False),          # 2026-11-16 12:00:01.5 / 2026-11-16T12:00:01
    (_with_time("%d.%m.%Y"), False),
    (_with_time("%d.%m.%y"), False),
    (_with_time("%d/%m/%Y"), False),
    (_with_time("%m/%d/%Y"), False),
    (_with_time("%Y/%m/%d"), False),
    (("%H:%M:%S.%f", "%H:%M:%S", "%H:%M"), True),
]
MIN_SUCCESS = 0.6   # Anteil lesbarer Werte; einzelne Fehlerzeilen eines Loggers sind erlaubt
_DAY = 86400.0


def _parse_group(text: pd.Series, formats: tuple[str, ...]) -> pd.Series:
    result = None
    for fmt in formats:
        try:
            parsed = pd.to_datetime(text, format=fmt, errors="coerce")
        except (ValueError, TypeError):
            continue
        result = parsed if result is None else result.fillna(parsed)
    return result if result is not None else pd.Series(pd.NaT, index=text.index)


def looks_like_datetime(value) -> bool:
    """Schnelle Vorprüfung, ob ein Text wie Datum/Uhrzeit aussieht."""
    if not isinstance(value, str):
        return False
    text = value.strip()
    return bool(text) and (_DATE_RE.match(text) is not None or _TIME_RE.match(text) is not None)


def parse_datetime_strings(values) -> Optional[tuple[np.ndarray, str]]:
    """Text-Zeitstempel in Sekunden umrechnen.

    Returns:
        (Sekunden je Wert, NaN wenn unlesbar; erkanntes Format) oder None, wenn die Werte nicht
        überwiegend als Datum/Uhrzeit lesbar sind. Reine Uhrzeiten werden als Sekunden seit
        Mitternacht geliefert; ein Sprung über Mitternacht wird erkannt und weitergezählt.
    """
    raw = pd.Series(values, dtype=object)
    text = raw.where(raw.notna(), "").astype(str).str.strip().str.replace(",", ".", regex=False)
    filled = text != ""
    if not filled.any():
        return None
    sample = text[filled].head(300)

    best = None
    for formats, time_only in FORMAT_GROUPS:
        share = float(_parse_group(sample, formats).notna().mean())
        if best is None or share > best[0]:
            best = (share, formats, time_only)
    if best is None or best[0] < MIN_SUCCESS:
        return None

    _, formats, time_only = best
    parsed = _parse_group(text.where(filled, ""), formats)
    # np.array: Kopie, da pandas 3 schreibgeschützte Arrays liefert
    if time_only:
        seconds = np.array((parsed - parsed.dt.normalize()).dt.total_seconds().to_numpy(dtype=float))
        valid = np.flatnonzero(np.isfinite(seconds))
        if len(valid) > 1:
            jumps = np.diff(seconds[valid]) < -_DAY / 2   # Uhrzeit springt zurück: neuer Tag
            seconds[valid[1:]] += np.cumsum(jumps) * _DAY
    else:
        seconds = np.array((parsed - pd.Timestamp("1970-01-01")).dt.total_seconds().to_numpy(dtype=float))
    return seconds, formats[0]
