"""Tests für das Einlesen verschiedener Dateiformate."""

import numpy as np
import pytest

from graph_plotter.loaders import (WHITESPACE, default_spec, detect_delimiter, load_datasets,
                                   read_table, to_numbers)
from graph_plotter.timeparse import looks_like_datetime, parse_datetime_strings


def write(tmp_path, name, text, encoding="utf-8", bom=b""):
    path = tmp_path / name
    path.write_bytes(bom + text.encode(encoding))
    return str(path)


def load(path):
    table = read_table(path)
    return table, load_datasets(default_spec(path, table), table)


# --------------------------------------------------------------------------- Trennzeichen

@pytest.mark.parametrize("text, expected", [
    ("t  U  I\n0,0  1,5  2,5\n0,1  1,6  2,6\n", WHITESPACE),       # Leerzeichen + Dezimalkomma
    ("t U\n0.0 1.5\n0.1 1.6\n", WHITESPACE),
    ("t, U\n0.0, 1.5\n0.1, 1.6\n", ","),                             # Komma mit Leerzeichen
    ("t;U\n0,0;1,5\n0,1;1,6\n", ";"),
    ("t\tU\n0,0\t1,5\n", "\t"),
])
def test_detect_delimiter_variants(text, expected):
    assert detect_delimiter(text) is expected if expected is None else detect_delimiter(text) == expected


def test_whitespace_separated_device_file(tmp_path):
    text = ("# Messgerät XY\n# Datum: 16.11.2026\n"
            "Zeit   Spannung   Strom\n"
            "  0,000    1,50E-3    2,0\n"
            "  0,001    1,60E-3    2,1\n"
            "  0,002    1,70E-3    2,2\n")
    table, result = load(write(tmp_path, "geraet.dat", text))
    assert table.delimiter is WHITESPACE and table.decimal == ","
    assert [d.source_column for d in result.datasets] == ["Spannung", "Strom"]
    assert result.datasets[0].y.tolist() == pytest.approx([1.5e-3, 1.6e-3, 1.7e-3])
    assert result.datasets[0].x.tolist() == pytest.approx([0.0, 0.001, 0.002])


@pytest.mark.parametrize("encoding, bom", [("utf-16-le", b"\xff\xfe"), ("utf-16-le", b""), ("utf-16-be", b"\xfe\xff")])
def test_utf16(tmp_path, encoding, bom):
    # So speichert Excel „Unicode-Text“: UTF-16, Tab-getrennt
    path = write(tmp_path, "unicode.txt", "Zeit\tTemperatur °C\n0\t20,5\n1\t21,5\n", encoding, bom)
    table, result = load(path)
    assert "UTF-16" in table.info
    assert result.datasets[0].source_column == "Temperatur °C"
    assert result.datasets[0].y.tolist() == [20.5, 21.5]


def test_thousands_separator_and_odd_values_fall_back(tmp_path):
    path = write(tmp_path, "t.csv", "x;y\n1;1.000,5\n2;−2,5\n3;abc\n4;7\n")
    _, result = load(path)
    ds = result.datasets[0]
    assert ds.x.tolist() == [1, 2, 4]
    assert ds.y.tolist() == [1000.5, -2.5, 7]


def test_ragged_and_trailing_delimiters(tmp_path):
    path = write(tmp_path, "r.csv", "x;a;b;\n0;1;2;\n1;2\n2;3;4;5;6\n3;4;5;\n")
    _, result = load(path)
    a, b = result.datasets[:2]
    assert a.x.tolist() == [0, 1, 2, 3] and a.y.tolist() == [1, 2, 3, 4]
    assert b.x.tolist() == [0, 2, 3]


def test_skipped_rows_counts_only_rows_with_content(tmp_path):
    path = write(tmp_path, "s.csv", "x;y\n0;1\n1;2\n;;\nkaputt;3\n\n2;3\n")
    _, result = load(path)
    assert result.skipped_rows == 1
    assert result.datasets[0].x.tolist() == [0, 1, 2]


# --------------------------------------------------------------------------- Datum/Uhrzeit

@pytest.mark.parametrize("values, expected", [
    (["2026-11-16 12:00:00", "2026-11-16 12:00:01.5", "2026-11-16 12:00:03"], [0, 1.5, 3]),
    (["2026-11-16T12:00:00", "2026-11-16T12:01:00"], [0, 60]),
    (["16.11.2026 12:00:00", "16.11.2026 12:00:01,25", "16.11.2026 12:00:02"], [0, 1.25, 2]),
    (["16.11.2026 23:59", "17.11.2026 00:01"], [0, 120]),
    (["16.11.2026", "17.11.2026"], [0, 86400]),
    (["12:00:00", "12:00:00,5", "12:00:02"], [0, 0.5, 2]),
    (["23:59:59", "00:00:01"], [0, 2]),     # Sprung über Mitternacht
])
def test_parse_datetime_strings(values, expected):
    seconds, _ = parse_datetime_strings(values)
    assert (seconds - seconds[0]).tolist() == pytest.approx(expected)


def test_parse_datetime_rejects_numbers_and_text():
    assert parse_datetime_strings(["1", "2", "3"]) is None
    assert parse_datetime_strings(["abc", "def"]) is None
    assert looks_like_datetime("16.11.2026 12:00") and not looks_like_datetime("1,5")


def test_csv_with_logger_timestamps(tmp_path):
    text = "Zeitstempel;Temperatur\n16.11.2026 08:00:00;20,1\n16.11.2026 08:00:10;20,3\n" \
           "Fehler;--\n16.11.2026 08:00:20;20,6\n"
    _, result = load(write(tmp_path, "logger.csv", text))
    assert result.x_is_time and result.skipped_rows == 1
    assert result.datasets[0].x.tolist() == [0, 10, 20]
    assert result.datasets[0].y.tolist() == [20.1, 20.3, 20.6]


# --------------------------------------------------------------------------- Zahlen

def test_to_numbers_fast_and_fallback():
    import pandas as pd
    s = pd.Series([1.0, "2,5", "3.5", True, None, "", "1.234.567", "x"], dtype=object)
    result = to_numbers(s, decimal=",")
    assert result[:3].tolist() == [1.0, 2.5, 3.5]
    assert np.isnan(result[3]) and np.isnan(result[4]) and np.isnan(result[5])
    assert result[6] == 1234567 and np.isnan(result[7])


def test_large_csv_is_fast(tmp_path):
    import time
    n = 200_000
    rows = "\n".join(f"{i * 0.001:.3f};{np.sin(i / 100):.6f};{np.cos(i / 100):.6f}".replace(".", ",") for i in range(n))
    path = write(tmp_path, "gross.csv", "t;a;b\n" + rows)
    start = time.perf_counter()
    _, result = load(path)
    elapsed = time.perf_counter() - start
    assert result.datasets[0].n_points == n
    assert elapsed < 3, f"{elapsed:.1f} s"
