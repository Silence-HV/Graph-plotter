"""Projektdateien (*.gplot, JSON): geladene Dateien, Import-Einstellungen und Plot-Einstellungen."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from . import VERSION
from .loaders import LoadError, Table, load_datasets, read_table
from .model import Dataset, ImportSpec
from .plotting import PlotSettings

PROJECT_EXTENSION = ".gplot"
FORMAT_VERSION = 1


@dataclass
class ProjectData:
    datasets: list[Dataset]
    settings: PlotSettings
    problems: list[str] = field(default_factory=list)


def save_project(path: str, datasets: list[Dataset], settings: PlotSettings) -> None:
    base = Path(path).resolve().parent
    entries = []
    for ds in datasets:
        if ds.spec is None:
            continue
        spec = ds.spec.to_dict()
        abs_path = str(Path(spec["path"]).resolve())
        spec["path"] = abs_path
        try:
            spec["relative_path"] = os.path.relpath(abs_path, base)
        except ValueError:  # anderes Laufwerk
            spec["relative_path"] = None
        entries.append({"spec": spec, "style": ds.style_dict()})

    data = {
        "app": "GraphPlotter",
        "app_version": VERSION,
        "format": FORMAT_VERSION,
        "settings": settings.to_dict(),
        "datasets": entries,
    }
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _resolve(spec: dict, base: Path) -> str | None:
    candidates = []
    if spec.get("relative_path"):
        candidates.append(base / spec["relative_path"])
    if spec.get("path"):
        candidates.append(Path(spec["path"]))
    for candidate in candidates:
        if candidate.exists():
            return str(candidate.resolve())
    return None


def load_project(path: str) -> ProjectData:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LoadError(f"Projektdatei kann nicht gelesen werden: {exc}") from exc
    if not isinstance(data, dict) or "datasets" not in data:
        raise LoadError("Keine gültige Graph-Plotter-Projektdatei.")

    settings = PlotSettings.from_dict(data.get("settings", {}))
    base = Path(path).resolve().parent
    tables: dict[tuple, Table] = {}
    datasets: list[Dataset] = []
    problems: list[str] = []

    for entry in data["datasets"]:
        raw_spec = dict(entry.get("spec", {}))
        resolved = _resolve(raw_spec, base)
        if resolved is None:
            problems.append(f"Datei nicht gefunden: {raw_spec.get('path', '?')}")
            continue
        raw_spec["path"] = resolved
        spec = ImportSpec.from_dict(raw_spec)
        key = (spec.path, spec.sheet)
        try:
            if key not in tables:
                tables[key] = read_table(spec.path, spec.sheet)
            result = load_datasets(spec, tables[key])
        except LoadError as exc:
            problems.append(f"{Path(spec.path).name}: {exc}")
            continue
        if not result.datasets:
            problems.append(f"{Path(spec.path).name}: keine gültigen Daten mehr in der gewählten Spalte.")
            continue
        ds = result.datasets[0]
        ds.apply_style(entry.get("style", {}))
        datasets.append(ds)

    return ProjectData(datasets, settings, problems)
