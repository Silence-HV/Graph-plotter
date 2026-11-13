"""Zahlen aus Zellen und Eingabefeldern lesen (deutsche und englische Schreibweise)."""

from __future__ import annotations

import datetime as _dt
import math
from typing import Optional

_MINUS_SIGNS = ("−", "–")  # typografisches Minus, Halbgeviertstrich
_SPACES = (" ", " ", " ", "'")  # Leerzeichen, geschützte Leerzeichen, Schweizer Tausendertrenner


def parse_number(value) -> float:
    """Wandle einen Zellen- oder Texteingabewert in float um.

    Unterstützt:
    - Zahlen (int/float) direkt
    - Dezimalkomma ("3,14") und Dezimalpunkt ("3.14")
    - Tausendertrenner ("1.000,5", "1,000.5", "1 000,5")
    - E-Notation ("1,5E+9", "2.3e-6")

    Ist nur ein einzelnes Trennzeichen vorhanden, gilt es als Dezimaltrenner.
    Mehrere gleiche Trennzeichen ohne weiteres Trennzeichen gelten als Tausendertrenner.

    Raises:
        ValueError: wenn der Wert leer ist oder nicht als Zahl gelesen werden kann.
    """
    if value is None:
        raise ValueError("Leerer Wert")
    if isinstance(value, bool):
        raise ValueError("Wahrheitswert ist keine Zahl")
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    for ch in _SPACES:
        text = text.replace(ch, "")
    for ch in _MINUS_SIGNS:
        text = text.replace(ch, "-")
    if not text:
        raise ValueError("Leerer Text")

    # Exponent abtrennen, damit Trennzeichen nur in der Mantisse ausgewertet werden
    mantissa, exponent = text, ""
    for marker in ("E", "e"):
        if marker in text:
            mantissa, _, rest = text.partition(marker)
            exponent = "e" + rest
            break

    n_comma = mantissa.count(",")
    n_dot = mantissa.count(".")
    if n_comma and n_dot:
        # Das zuletzt stehende Zeichen ist der Dezimaltrenner
        if mantissa.rfind(",") > mantissa.rfind("."):
            mantissa = mantissa.replace(".", "").replace(",", ".")
        else:
            mantissa = mantissa.replace(",", "")
    elif n_comma == 1:
        mantissa = mantissa.replace(",", ".")
    elif n_comma > 1:
        mantissa = mantissa.replace(",", "")
    elif n_dot > 1:
        mantissa = mantissa.replace(".", "")

    try:
        return float(mantissa + exponent)
    except ValueError:
        raise ValueError(f"'{value}' ist keine gültige Zahl") from None


def parse_optional(text: str) -> Optional[float]:
    """Lese ein optionales Eingabefeld: leer -> None, sonst Zahl (ValueError bei ungültiger Eingabe)."""
    if text is None or not str(text).strip():
        return None
    result = parse_number(text)
    if not math.isfinite(result):
        raise ValueError(f"'{text}' ist keine endliche Zahl")
    return result


def is_number(value) -> bool:
    """True, wenn parse_number den Wert lesen kann."""
    try:
        parse_number(value)
        return True
    except ValueError:
        return False


def to_seconds(value) -> Optional[float]:
    """Datum/Uhrzeit/Zeitspanne in Sekunden umrechnen, sonst None."""
    if isinstance(value, _dt.datetime):
        return value.timestamp() if value.tzinfo else value.replace(tzinfo=_dt.timezone.utc).timestamp()
    if isinstance(value, _dt.date):
        return _dt.datetime(value.year, value.month, value.day, tzinfo=_dt.timezone.utc).timestamp()
    if isinstance(value, _dt.time):
        return value.hour * 3600 + value.minute * 60 + value.second + value.microsecond / 1e6
    if isinstance(value, _dt.timedelta):
        return value.total_seconds()
    return None
