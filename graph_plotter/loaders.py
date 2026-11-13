"""CSV- und Excel-Dateien einlesen und in Datensätze umwandeln."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Optional

import numpy as np

from .model import Dataset, ImportSpec
from .numparse import is_number, parse_number, to_seconds

CSV_EXTENSIONS = (".csv", ".txt", ".tsv", ".dat")
EXCEL_EXTENSIONS = (".xlsx", ".xlsm", ".xls")
SUPPORTED_EXTENSIONS = CSV_EXTENSIONS + EXCEL_EXTENSIONS


class LoadError(Exception):
    """Datei konnte nicht gelesen werden (Meldung ist für Nutzer formuliert)."""


@dataclass
class Table:
    """Rohinhalt einer Datei: Zeilen mit Zellwerten (Text, Zahl, Datum oder None)."""

    rows: list[list]
    sheets: list[str] = field(default_factory=list)
    sheet: Optional[str] = None
    info: str = ""  # z. B. "Trennzeichen ';', Kodierung cp1252"

    @property
    def width(self) -> int:
        return max((len(r) for r in self.rows), default=0)


@dataclass
class LoadResult:
    datasets: list[Dataset]
    skipped_rows: int = 0
    empty_columns: list[str] = field(default_factory=list)
    x_is_time: bool = False


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
# Lesen
# ---------------------------------------------------------------------------

def _decode(raw: bytes) -> tuple[str, str]:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1"), "latin-1"


def detect_delimiter(text: str) -> str:
    """Trennzeichen erkennen. Ausgewertet werden die letzten Zeilen (Metadaten stehen meist oben)."""
    lines = [line for line in text.splitlines() if line.strip()]
    sample = lines[-30:]
    if not sample:
        return ","
    # Tab und Semikolon haben Vorrang, weil ein Komma auch Dezimaltrenner sein kann.
    # Einzelne Zeilen ohne Trennzeichen (Metadaten, Kommentare) werden toleriert.
    for delimiter in ("\t", ";", ","):
        share = sum(delimiter in line for line in sample) / len(sample)
        if share >= 0.6:
            return delimiter
    # Fallback: häufigstes Zeichen
    counts = {d: sum(line.count(d) for line in sample) for d in ("\t", ";", ",")}
    best = max(counts, key=counts.get)
    return best if counts[best] else ","


def read_csv(path: str) -> Table:
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        raise LoadError(f"Datei kann nicht gelesen werden: {exc}") from exc
    text, encoding = _decode(raw)
    delimiter = detect_delimiter(text)
    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    names = {"\t": "Tab", ";": "Semikolon", ",": "Komma"}
    return Table(_normalize(rows), info=f"Trennzeichen: {names[delimiter]}, Kodierung: {encoding}")


def _read_xlsx(path: str, sheet: Optional[str]) -> Table:
    from openpyxl import load_workbook

    try:
        wb = load_workbook(path, read_only=True, data_only=True)
    except Exception as exc:  # openpyxl wirft je nach Fehler verschiedene Typen
        raise LoadError(f"Excel-Datei kann nicht geöffnet werden: {exc}") from exc
    try:
        sheets = list(wb.sheetnames)
        if sheet is None:
            ws = wb.active if wb.active is not None else wb[sheets[0]]
        elif sheet in sheets:
            ws = wb[sheet]
        else:
            raise LoadError(f"Tabellenblatt „{sheet}“ nicht gefunden.")
        # Manche Programme speichern falsche Tabellengrößen; neu ermitteln lassen
        ws.reset_dimensions()
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
        return Table(_normalize(rows), sheets=sheets, sheet=ws.title)
    finally:
        wb.close()


def _read_xls(path: str, sheet: Optional[str]) -> Table:
    try:
        import xlrd
    except ImportError as exc:
        raise LoadError("Für alte Excel-Dateien (.xls) wird das Paket „xlrd“ benötigt "
                        "(pip install xlrd).") from exc
    try:
        book = xlrd.open_workbook(path)
    except Exception as exc:
        raise LoadError(f"Excel-Datei kann nicht geöffnet werden: {exc}") from exc
    sheets = book.sheet_names()
    if sheet is None:
        sh = book.sheet_by_index(0)
    elif sheet in sheets:
        sh = book.sheet_by_name(sheet)
    else:
        raise LoadError(f"Tabellenblatt „{sheet}“ nicht gefunden.")
    rows = []
    for r in range(sh.nrows):
        row = []
        for c in range(sh.ncols):
            cell = sh.cell(r, c)
            if cell.ctype == xlrd.XL_CELL_DATE:
                row.append(xlrd.xldate_as_datetime(cell.value, book.datemode))
            elif cell.ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK, xlrd.XL_CELL_ERROR):
                row.append(None)
            else:
                row.append(cell.value)
        rows.append(row)
    return Table(_normalize(rows), sheets=sheets, sheet=sh.name)


def read_table(path: str, sheet: Optional[str] = None) -> Table:
    """Datei als Tabelle lesen (CSV oder Excel)."""
    if not Path(path).exists():
        raise LoadError(f"Datei nicht gefunden: {path}")
    suffix = Path(path).suffix.lower()
    if suffix == ".xls":
        return _read_xls(path, sheet)
    if suffix in (".xlsx", ".xlsm"):
        return _read_xlsx(path, sheet)
    return read_csv(path)


# ---------------------------------------------------------------------------
# Aufbau erkennen
# ---------------------------------------------------------------------------

def _is_numeric_cell(cell) -> bool:
    return to_seconds(cell) is not None or is_number(cell)


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
    # Nichts Brauchbares gefunden: erste Zeile als Kopfzeile annehmen
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
# Datensätze erzeugen
# ---------------------------------------------------------------------------

def _to_float(cell) -> float:
    seconds = to_seconds(cell)
    if seconds is not None:
        return seconds
    return parse_number(cell)


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

    x_values: list[float] = []
    y_values: list[list[float]] = [[] for _ in y_cols]
    skipped = 0
    x_is_time = False
    start = max(spec.data_start, 0)
    if spec.header_row is not None:
        start = max(start, spec.header_row + 1)

    for row in table.rows[start:]:
        if all(_is_empty(c) for c in row):
            continue
        x_cell = row[spec.x_col]
        try:
            x_val = _to_float(x_cell)
        except ValueError:
            skipped += 1
            continue
        if to_seconds(x_cell) is not None:
            x_is_time = True
        x_values.append(x_val)
        for k, c in enumerate(y_cols):
            try:
                y_values[k].append(parse_number(row[c]))
            except ValueError:
                y_values[k].append(np.nan)

    x = np.asarray(x_values, dtype=float)
    ys = np.asarray(y_values, dtype=float).reshape(len(y_cols), len(x_values))

    if x_is_time and len(x):
        x = x - x[0]  # Sekunden ab erstem Messwert

    if spec.sort_x and len(x):
        order = np.argsort(x, kind="stable")
        x = x[order]
        ys = ys[:, order]

    stem = Path(spec.path).stem
    result = LoadResult(datasets=[], skipped_rows=skipped, x_is_time=x_is_time)

    if spec.statistics:
        if len(x) and np.isfinite(ys).any():
            ds = Dataset(name=f"{stem} (n={len(y_cols)})", x=x, y_raw=ys,
                         spec=replace(spec, y_cols=list(y_cols)), source_column="",
                         linestyle="--", linewidth=1.8, markersize=6, marker_filled=False)
            result.datasets.append(ds)
        return result

    for k, c in enumerate(y_cols):
        mask = np.isfinite(ys[k]) & np.isfinite(x)
        if not mask.any():
            result.empty_columns.append(names[c])
            continue
        result.datasets.append(Dataset(
            name=f"{stem} – {names[c]}", x=x[mask], y=ys[k][mask],
            spec=replace(spec, y_cols=[c]), source_column=names[c],
        ))
    return result
