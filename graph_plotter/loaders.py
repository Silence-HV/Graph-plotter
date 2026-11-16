"""CSV-, Text- und Tabellendateien einlesen und in Datensätze umwandeln.

Ablauf:
1. ``read_table`` liest die Datei und liefert eine Vorschau (erste Zeilen) für die Erkennung von
   Kopfzeile und Datenbeginn sowie für den Importdialog.
2. ``load_datasets`` liest die gewählten Spalten vollständig – spaltenweise und damit schnell
   (CSV über pandas, Tabellen über calamine). Nur Zellen, die der schnelle Weg nicht lesen kann
   (z. B. „1.000,5“), werden einzeln mit ``parse_number`` umgewandelt.
"""

from __future__ import annotations

import codecs
import csv
import io
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from .model import Dataset, ImportSpec
from .numparse import is_number, parse_number, to_seconds
from .timeparse import looks_like_datetime, parse_datetime_strings

CSV_EXTENSIONS = (".csv", ".txt", ".tsv", ".dat", ".asc", ".prn")
EXCEL_EXTENSIONS = (".xlsx", ".xlsm", ".xls", ".xlsb", ".ods")
SUPPORTED_EXTENSIONS = CSV_EXTENSIONS + EXCEL_EXTENSIONS
PREVIEW_ROWS = 1000          # Zeilen für Erkennung und Vorschau
WHITESPACE = None            # Trennzeichen „Leerraum“ (Leerzeichen/Tabs, auch mehrfach)

_STRICT_NUMBER = re.compile(r"^[+-]?(?:\d+(?:[.,]\d*)?|[.,]\d+)(?:[eE][+-]?\d+)?$")
_COMMA_DECIMAL = re.compile(r"^[+-]?\d*,\d+(?:[eE][+-]?\d+)?$")
_DOT_DECIMAL = re.compile(r"^[+-]?\d*\.\d+(?:[eE][+-]?\d+)?$")
_DELIMITER_NAMES = {"\t": "Tab", ";": "Semikolon", ",": "Komma", WHITESPACE: "Leerzeichen"}


class LoadError(Exception):
    """Datei konnte nicht gelesen werden (Meldung ist für Nutzer formuliert)."""


@dataclass
class Table:
    """Inhalt einer Datei.

    ``rows`` enthält nur die ersten ``PREVIEW_ROWS`` Zeilen (Erkennung, Vorschau). Die vollständigen
    Daten liegen in ``text`` (CSV) bzw. ``all_rows`` (Tabellenblatt) und werden erst beim Laden der
    gewählten Spalten ausgewertet.
    """

    rows: list[list]
    sheets: list[str] = field(default_factory=list)
    sheet: Optional[str] = None
    info: str = ""
    n_rows: int = 0
    kind: str = "csv"                     # "csv" oder "sheet"
    text: Optional[str] = None
    delimiter: Optional[str] = ","
    decimal: str = "."
    all_rows: Optional[list[list]] = None

    @property
    def width(self) -> int:
        return max((len(r) for r in self.rows), default=0)


@dataclass
class LoadResult:
    datasets: list[Dataset]
    skipped_rows: int = 0
    empty_columns: list[str] = field(default_factory=list)
    x_is_time: bool = False
    time_format: str = ""


def is_supported(path: str) -> bool:
    return Path(path).suffix.lower() in SUPPORTED_EXTENSIONS


def is_excel(path: str) -> bool:
    return Path(path).suffix.lower() in EXCEL_EXTENSIONS


def _is_empty(cell) -> bool:
    return cell is None or (isinstance(cell, str) and not cell.strip())


def _normalize(rows: list[list]) -> list[list]:
    """Leere Zeilen am Ende entfernen und alle Zeilen auf gleiche Breite bringen."""
    rows = [list(r) for r in rows]
    while rows and all(_is_empty(c) for c in rows[-1]):
        rows.pop()
    width = 0
    for r in rows:
        for i in range(len(r) - 1, -1, -1):
            if not _is_empty(r[i]):
                width = max(width, i + 1)
                break
    return [(r + [None] * width)[:width] for r in rows]


# ---------------------------------------------------------------------------
# Textdateien
# ---------------------------------------------------------------------------

def decode(raw: bytes) -> tuple[str, str]:
    """Bytes in Text umwandeln: UTF-16 (mit/ohne BOM), UTF-8, Windows-1252, Latin-1."""
    if raw.startswith(codecs.BOM_UTF16_LE) or raw.startswith(codecs.BOM_UTF16_BE):
        return raw.decode("utf-16"), "UTF-16"
    head = raw[:4000]
    if len(head) >= 4:
        zeros_odd = head[1::2].count(0) / max(1, len(head[1::2]))
        zeros_even = head[0::2].count(0) / max(1, len(head[0::2]))
        if zeros_odd > 0.3 and zeros_even < 0.05:
            return raw.decode("utf-16-le", errors="replace"), "UTF-16"
        if zeros_even > 0.3 and zeros_odd < 0.05:
            return raw.decode("utf-16-be", errors="replace"), "UTF-16"
    for encoding, name in (("utf-8-sig", "UTF-8"), ("cp1252", "Windows-1252")):
        try:
            return raw.decode(encoding), name
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1"), "Latin-1"


def _split(line: str, delimiter: Optional[str]) -> list[str]:
    if delimiter is WHITESPACE:
        return line.split()
    return next(csv.reader([line], delimiter=delimiter), [])


def detect_delimiter(text: str) -> Optional[str]:
    """Trennzeichen erkennen: Tab, Semikolon, Komma oder Leerraum (``None``).

    Bewertet je Kandidat, wie gleichmäßig die Spaltenzahl ist und wie viele Felder echte Zahlen
    sind – so wird z. B. „0,5 1,5“ als Leerraum mit Dezimalkomma erkannt und „0.5, 1.5“ als Komma.
    Ausgewertet werden die letzten Zeilen (Metadaten stehen meist oben).
    """
    lines = [line for line in text.split("\n")[-200:] if line.strip()][-40:]
    if not lines:
        return ","
    best, best_score = ",", -1.0
    for delimiter in ("\t", ";", ",", WHITESPACE):  # Reihenfolge = Vorrang bei Gleichstand
        counts, numeric = [], []
        for line in lines:
            fields = [f.strip().strip('"') for f in _split(line.rstrip("\r"), delimiter)]
            counts.append(len(fields))
            if len(fields) >= 2:
                numeric.append(sum(bool(_STRICT_NUMBER.match(f)) for f in fields if f) / len(fields))
            else:
                numeric.append(0.0)
        mode = max(set(counts), key=counts.count)
        if mode < 2:
            continue
        consistency = counts.count(mode) / len(counts)
        score = 0.7 * float(np.mean(numeric)) + 0.3 * consistency
        if score > best_score + 1e-9:
            best, best_score = delimiter, score
    return best


def _detect_decimal(rows: list[list], delimiter: Optional[str]) -> str:
    if delimiter == ",":
        return "."
    comma = dot = 0
    for row in rows:
        for cell in row:
            if isinstance(cell, str):
                text = cell.strip()
                comma += bool(_COMMA_DECIMAL.match(text))
                dot += bool(_DOT_DECIMAL.match(text))
    return "," if comma > dot else "."


def read_csv(path: str) -> Table:
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        raise LoadError(f"Datei kann nicht gelesen werden: {exc}") from exc
    text, encoding = decode(raw)
    if "\n" not in text and "\r" in text:      # alte Mac-Zeilenenden
        text = text.replace("\r", "\n")
    delimiter = detect_delimiter(text)
    lines = text.split("\n", PREVIEW_ROWS)[:PREVIEW_ROWS]
    rows = [_split(line.rstrip("\r"), delimiter) if line.strip() else [] for line in lines]
    rows = _normalize(rows)
    decimal = _detect_decimal(rows, delimiter)
    n_rows = text.count("\n") + (0 if text.endswith("\n") else 1)
    info = f"Trennzeichen: {_DELIMITER_NAMES[delimiter]}, Dezimal{'komma' if decimal == ',' else 'punkt'}, " \
           f"Kodierung: {encoding}"
    return Table(rows, info=info, n_rows=n_rows, kind="csv", text=text, delimiter=delimiter, decimal=decimal)


# ---------------------------------------------------------------------------
# Tabellendateien
# ---------------------------------------------------------------------------

def _read_with_calamine(path: str, sheet: Optional[str]) -> Table:
    import python_calamine

    try:
        book = python_calamine.load_workbook(path)
    except Exception as exc:  # calamine meldet verschiedene Fehlertypen (Passwort, ZIP, XML …)
        raise LoadError(f"Tabellendatei kann nicht geöffnet werden: {exc}") from exc
    sheets = list(book.sheet_names)
    if not sheets:
        raise LoadError("Die Datei enthält keine Tabellenblätter.")
    if sheet is None:
        sheet = sheets[0]
    elif sheet not in sheets:
        raise LoadError(f"Tabellenblatt „{sheet}“ nicht gefunden.")
    data = book.get_sheet_by_name(sheet)
    try:
        rows = data.to_python(skip_empty_area=False)
    except TypeError:
        rows = data.to_python()
    rows = _normalize(rows)
    return Table(rows[:PREVIEW_ROWS], sheets=sheets, sheet=sheet, n_rows=len(rows), kind="sheet",
                 all_rows=rows, info=f"Tabellenblatt „{sheet}“")


def _read_with_openpyxl(path: str, sheet: Optional[str]) -> Table:
    from openpyxl import load_workbook

    try:
        wb = load_workbook(path, read_only=True, data_only=True)
    except Exception as exc:
        raise LoadError(f"Excel-Datei kann nicht geöffnet werden: {exc}") from exc
    try:
        sheets = list(wb.sheetnames)
        if sheet is not None and sheet not in sheets:
            raise LoadError(f"Tabellenblatt „{sheet}“ nicht gefunden.")
        ws = wb[sheet] if sheet else (wb.active if wb.active is not None else wb[sheets[0]])
        ws.reset_dimensions()
        rows = _normalize([list(r) for r in ws.iter_rows(values_only=True)])
        return Table(rows[:PREVIEW_ROWS], sheets=sheets, sheet=ws.title, n_rows=len(rows), kind="sheet",
                     all_rows=rows, info=f"Tabellenblatt „{ws.title}“")
    finally:
        wb.close()


def read_table(path: str, sheet: Optional[str] = None) -> Table:
    """Datei lesen (Text oder Tabelle) und Vorschau erzeugen."""
    if not Path(path).exists():
        raise LoadError(f"Datei nicht gefunden: {path}")
    if not is_excel(path):
        return read_csv(path)
    try:
        return _read_with_calamine(path, sheet)
    except ImportError:
        if Path(path).suffix.lower() in (".xlsx", ".xlsm"):
            return _read_with_openpyxl(path, sheet)
        raise LoadError("Für dieses Tabellenformat wird das Paket „python-calamine“ benötigt.") from None


# ---------------------------------------------------------------------------
# Aufbau erkennen
# ---------------------------------------------------------------------------

def _is_numeric_cell(cell) -> bool:
    return to_seconds(cell) is not None or looks_like_datetime(cell) or is_number(cell)


def _numeric_count(row: list) -> int:
    return sum(1 for c in row if not _is_empty(c) and _is_numeric_cell(c))


def detect_layout(rows: list[list]) -> tuple[Optional[int], int]:
    """Kopfzeile und erste Datenzeile erkennen.

    Datenbeginn ist die erste Zeile mit mindestens zwei Zahlen, auf die eine weitere solche Zeile
    folgt (oder die die letzte Zeile ist). Die Zeile direkt davor gilt als Kopfzeile, wenn sie
    Text enthält.

    Returns:
        (header_row, data_start), header_row ist None, wenn es keine Kopfzeile gibt.
    """
    n = len(rows)
    for r in range(n):
        if _numeric_count(rows[r]) < 2:
            continue
        if r + 1 < n and _numeric_count(rows[r + 1]) < 2:
            continue
        if r > 0:
            prev = rows[r - 1]
            filled = [c for c in prev if not _is_empty(c)]
            if filled and _numeric_count(prev) < len(filled):
                return r - 1, r
        return None, r
    return (0, 1) if n > 1 else (None, 0)


def column_names(table: Table, header_row: Optional[int]) -> list[str]:
    """Spaltennamen aus der Kopfzeile, leere Namen werden durch „Spalte N“ ersetzt."""
    width = table.width
    header = table.rows[header_row] if header_row is not None and header_row < len(table.rows) else []
    names: list[str] = []
    seen: dict[str, int] = {}
    for i in range(width):
        cell = header[i] if i < len(header) else None
        name = str(cell).strip() if not _is_empty(cell) else f"Spalte {i + 1}"
        if name in seen:
            seen[name] += 1
            name = f"{name} ({seen[name]})"
        else:
            seen[name] = 1
        names.append(name)
    return names


def default_spec(path: str, table: Optional[Table] = None, statistics: bool = False) -> ImportSpec:
    """Import-Einstellungen mit automatisch erkannter Kopfzeile."""
    table = table if table is not None else read_table(path)
    header_row, data_start = detect_layout(table.rows)
    return ImportSpec(path=str(path), sheet=table.sheet, header_row=header_row,
                      data_start=data_start, x_col=0, y_cols=[], statistics=statistics)


# ---------------------------------------------------------------------------
# Spalten vollständig lesen
# ---------------------------------------------------------------------------

def _line_offset(text: str, line: int) -> int:
    offset = 0
    for _ in range(line):
        nxt = text.find("\n", offset)
        if nxt < 0:
            return len(text)
        offset = nxt + 1
    return offset


def _raw_columns(table: Table, start: int, cols: list[int]) -> tuple[dict[int, pd.Series], np.ndarray]:
    """Gewählte Spalten ab Zeile ``start`` als pandas-Serien; dazu „Zeile hat Inhalt“."""
    if table.kind == "csv":
        data = table.text[_line_offset(table.text, start):]
        # pandas liest Zahlen (inkl. Dezimalkomma) selbst; Spalten mit unlesbaren Werten bleiben
        # Text und werden danach von to_numbers nachbearbeitet.
        options = dict(header=None, skip_blank_lines=True, decimal=table.decimal, on_bad_lines="skip",
                       engine="c", low_memory=False, keep_default_na=False, na_values=[""],
                       sep=r"\s+" if table.delimiter is WHITESPACE else table.delimiter)
        try:
            # Nur die gewählten Spalten lesen (schnell, sparsam) …
            frame = pd.read_csv(io.StringIO(data), usecols=cols, **options)
        except pd.errors.EmptyDataError:
            frame = pd.DataFrame(columns=cols)
        except (pd.errors.ParserError, ValueError):
            # … oder, wenn die ersten Zeilen kürzer sind als die gewählte Spalte, alle Spalten mit
            # festen Namen (fehlende Felder werden leer).
            n_names = max(table.width, max(cols) + 1) + 2
            try:
                frame = pd.read_csv(io.StringIO(data), names=list(range(n_names)), **options)
            except (pd.errors.ParserError, ValueError) as exc:
                raise LoadError(f"Die Datei kann nicht als Tabelle gelesen werden: {exc}") from exc
        columns = {c: frame[c] if c in frame else pd.Series([], dtype=object) for c in cols}
        has_content = frame.notna().any(axis=1).to_numpy() if len(frame) else np.zeros(0, dtype=bool)
        return columns, has_content

    rows = table.all_rows[start:]
    # Leere Zellen (calamine: "") als None, damit reine Zahlenspalten direkt umgewandelt werden können
    columns = {c: pd.Series([None if (v := (row[c] if c < len(row) else None)) == "" else v for row in rows],
                            dtype=object) for c in cols}
    has_content = np.array([any(not _is_empty(v) for v in row) for row in rows], dtype=bool) \
        if rows else np.zeros(0, dtype=bool)
    return columns, has_content


def _parse_or_nan(value) -> float:
    try:
        return parse_number(value)
    except ValueError:
        return np.nan


def to_numbers(series: pd.Series, decimal: str = ".") -> np.ndarray:
    """Spalte in float umwandeln: schneller Weg für normale Zahlen, Einzelprüfung nur für den Rest."""
    if len(series) == 0:
        return np.zeros(0)
    if pd.api.types.is_numeric_dtype(series.dtype) and not pd.api.types.is_bool_dtype(series.dtype):
        return series.to_numpy(dtype=float, na_value=np.nan)
    values = series.astype(object)
    # Schnellster Weg: Spalte enthält nur Zahlen und leere Zellen (typisch für Tabellenblätter)
    try:
        plain = values.tolist()
        if not any(isinstance(v, (str, bool)) for v in plain):
            return np.array(plain, dtype=float)
    except (TypeError, ValueError):
        pass
    is_text = values.map(lambda v: isinstance(v, str)).to_numpy(dtype=bool)
    candidate = values.copy()
    if decimal == "," and is_text.any():
        candidate[is_text] = values[is_text].str.replace(",", ".", regex=False)
    is_bool = values.map(lambda v: isinstance(v, bool)).to_numpy(dtype=bool)
    candidate[is_bool] = np.nan
    # Kopie: pandas 3 liefert schreibgeschützte Arrays (Copy-on-Write)
    numbers = np.array(pd.to_numeric(candidate, errors="coerce").to_numpy(dtype=float, na_value=np.nan))
    # Was der schnelle Weg nicht lesen konnte (Tausendertrenner, typografisches Minus …) einzeln prüfen
    retry = np.isnan(numbers) & is_text
    if retry.any():
        texts = values[retry]
        filled = texts.str.strip() != ""
        idx = np.flatnonzero(retry)[filled.to_numpy(dtype=bool)]
        if len(idx):
            numbers[idx] = [_parse_or_nan(v) for v in values.iloc[idx]]
    return numbers


def _x_values(series: pd.Series, decimal: str) -> tuple[np.ndarray, bool, str]:
    """X-Spalte lesen: Zahlen, Datums-/Zeitzellen oder Zeitstempel als Text."""
    first = next((v for v in series if not _is_empty(v)), None)
    if first is not None and to_seconds(first) is not None:
        values = np.array([s if (s := to_seconds(v)) is not None else np.nan for v in series], dtype=float)
        return values, True, "Datum/Uhrzeit"
    numbers = to_numbers(series, decimal)
    filled = series.map(lambda v: not _is_empty(v)).to_numpy(dtype=bool)
    if filled.any() and np.isfinite(numbers[filled]).mean() < 0.5 and looks_like_datetime(first):
        parsed = parse_datetime_strings(series.to_numpy())
        if parsed is not None:
            return parsed[0], True, parsed[1]
    return numbers, False, ""


def load_datasets(spec: ImportSpec, table: Optional[Table] = None) -> LoadResult:
    """Datensätze gemäß ``spec`` erzeugen."""
    if table is None:
        table = read_table(spec.path, spec.sheet)
    names = column_names(table, spec.header_row)
    width = len(names)
    if width < 2:
        raise LoadError("Die Datei muss mindestens zwei Spalten enthalten (X-Werte und Y-Werte).")
    if not 0 <= spec.x_col < width:
        raise LoadError(f"X-Spalte {spec.x_col + 1} existiert nicht.")
    y_cols = [c for c in (spec.y_cols or range(width)) if c != spec.x_col and 0 <= c < width]
    if not y_cols:
        raise LoadError("Keine Y-Spalte ausgewählt.")

    start = max(spec.data_start, 0)
    if spec.header_row is not None:
        start = max(start, spec.header_row + 1)

    columns, has_content = _raw_columns(table, start, [spec.x_col] + y_cols)
    x, x_is_time, time_format = _x_values(columns[spec.x_col], table.decimal)
    ys = np.vstack([to_numbers(columns[c], table.decimal) for c in y_cols]) if len(x) \
        else np.zeros((len(y_cols), 0))

    valid_x = np.isfinite(x)
    skipped = int(np.sum(~valid_x & has_content[:len(x)])) if len(has_content) else 0
    x = x[valid_x]
    ys = ys[:, valid_x]

    if x_is_time and len(x):
        x = x - x[0]  # Sekunden ab erstem Messwert
    if spec.sort_x and len(x):
        order = np.argsort(x, kind="stable")
        x = x[order]
        ys = ys[:, order]

    stem = Path(spec.path).stem
    result = LoadResult(datasets=[], skipped_rows=skipped, x_is_time=x_is_time, time_format=time_format)

    if spec.statistics:
        if len(x) and np.isfinite(ys).any():
            result.datasets.append(Dataset(
                name=f"{stem} (n={len(y_cols)})", x=x, y_raw=ys,
                spec=replace(spec, y_cols=list(y_cols)), source_column="",
                linestyle="--", linewidth=1.8, markersize=6, marker_filled=False))
        return result

    for k, c in enumerate(y_cols):
        mask = np.isfinite(ys[k])
        if not mask.any():
            result.empty_columns.append(names[c])
            continue
        result.datasets.append(Dataset(
            name=f"{stem} – {names[c]}", x=x[mask], y=ys[k][mask],
            spec=replace(spec, y_cols=[c]), source_column=names[c],
        ))
    return result
