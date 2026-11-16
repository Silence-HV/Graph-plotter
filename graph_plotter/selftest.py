"""Selbsttest des fertig gebauten Programms: ``GraphPlotter.exe --selbsttest``.

Prüft, ob alle Bestandteile in der ausgelieferten Fassung vorhanden sind und funktionieren
(Dateien lesen, Statistik, Export in alle Formate, Hauptfenster). Rückgabewert 0 = in Ordnung.
Das Protokoll steht in ``%TEMP%\\graphplotter_selbsttest.txt`` und in der Logdatei.
"""

from __future__ import annotations

import datetime as dt
import logging
import tempfile
import traceback
from pathlib import Path

log = logging.getLogger("graph_plotter.selftest")


def _write_samples(folder: Path) -> list[Path]:
    from openpyxl import Workbook

    csv_path = folder / "messung.csv"
    csv_path.write_text("Gerät: Test\nZeit;U1;U2\n" + "\n".join(
        f"{t / 10:.1f};{t * 0.5:.2f};{t * 0.6:.2f}".replace(".", ",") for t in range(50)), encoding="cp1252")
    dat_path = folder / "geraet.dat"
    dat_path.write_text("t  wert\n" + "\n".join(f"{t}  {t * t}" for t in range(50)), encoding="utf-16")
    log_path = folder / "logger.csv"
    start = dt.datetime(2026, 11, 16, 12, 0, 0)
    log_path.write_text("Zeit;T\n" + "\n".join(
        f"{(start + dt.timedelta(seconds=s)):%d.%m.%Y %H:%M:%S};{20 + s / 100:.2f}".replace(".", ",", 0)
        for s in range(0, 500, 10)), encoding="utf-8")
    xlsx_path = folder / "tabelle.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.append(["x", "a", "b", "c"])
    for i in range(50):
        ws.append([i, i + 0.1, i + 0.2, i - 0.1])
    wb.save(xlsx_path)
    return [csv_path, dat_path, log_path, xlsx_path]


def run_selftest() -> int:
    from .combine import combine_repeats
    from .exporting import FORMATS, ExportOptions, export_plot
    from .loaders import default_spec, load_datasets, read_table
    from .plotting import PlotSettings

    report: list[str] = []
    ok = True

    def check(name: str, function):
        nonlocal ok
        try:
            detail = function()
            report.append(f"OK      {name}{f' – {detail}' if detail else ''}")
        except Exception:
            ok = False
            report.append(f"FEHLER  {name}\n{traceback.format_exc()}")

    folder = Path(tempfile.mkdtemp(prefix="graphplotter_selbsttest_"))
    datasets = []

    def samples():
        return f"{len(_write_samples(folder))} Testdateien in {folder}"

    check("Testdateien schreiben", samples)
    for name in ("messung.csv", "geraet.dat", "logger.csv", "tabelle.xlsx"):
        def load(name=name):
            path = str(folder / name)
            table = read_table(path)
            result = load_datasets(default_spec(path, table), table)
            assert result.datasets, "keine Datensätze"
            datasets.extend(result.datasets)
            return f"{len(result.datasets)} Datensätze, {table.info}"
        check(f"Laden {name}", load)

    def combine():
        result = combine_repeats(datasets[-3:])
        datasets.append(result.dataset)
        return f"n = {result.dataset.n_repeats}"
    check("Messwiederholungen zusammenfassen", combine)

    for ext in FORMATS:
        def export(ext=ext):
            target = folder / f"plot.{ext}"
            export_plot(str(target), datasets, PlotSettings(), ExportOptions(width_in=6, height_in=4, dpi=100))
            assert target.stat().st_size > 0
            return f"{target.stat().st_size // 1024} KB"
        check(f"Export {ext.upper()}", export)

    def window():
        from PySide6.QtCore import QSettings
        from PySide6.QtWidgets import QApplication, QMessageBox

        from .ui import main_window

        for name in ("warning", "information", "critical"):
            setattr(QMessageBox, name, staticmethod(lambda *a, **k: None))
        app = QApplication.instance()
        win = main_window.MainWindow(QSettings(str(folder / "einstellungen.ini"), QSettings.Format.IniFormat))
        win.act_import_dialog.setChecked(False)
        win.add_files([str(folder / "messung.csv"), str(folder / "tabelle.xlsx")])
        assert win.replot(), "Plot fehlgeschlagen"
        for mode in ("dark", "light"):
            win.set_theme(mode, save=False)
        app.processEvents()
        count = len(win.datasets)
        win.close()
        return f"{count} Datensätze dargestellt"
    check("Hauptfenster", window)

    report.insert(0, f"Graph Plotter Selbsttest: {'BESTANDEN' if ok else 'FEHLGESCHLAGEN'}")
    text = "\n".join(report)
    log.info("%s", text)
    try:
        (Path(tempfile.gettempdir()) / "graphplotter_selbsttest.txt").write_text(text, encoding="utf-8")
    except OSError:
        pass
    return 0 if ok else 1
