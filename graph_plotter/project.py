"""Projektdateien (*.gplot, JSON): geladene Dateien, Import-Einstellungen und Plot-Einstellungen."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from . import VERSION
from .combine import combine_repeats
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


def _spec_entry(spec: ImportSpec, base: Path) -> dict:
    data = spec.to_dict()
    abs_path = str(Path(data["path"]).resolve())
    data["path"] = abs_path
    try:
        data["relative_path"] = os.path.relpath(abs_path, base)
    except ValueError:  # anderes Laufwerk
        data["relative_path"] = None
    return data


def save_project(path: str, datasets: list[Dataset], settings: PlotSettings) -> None:
    base = Path(path).resolve().parent
    entries = []
    for ds in datasets:
        if ds.is_combined:
            entries.append({"members": [_spec_entry(m, base) for m in ds.members],
                            "name": ds.name, "style": ds.style_dict()})
        elif ds.spec is not None:
            entries.append({"spec": _spec_entry(ds.spec, base), "style": ds.style_dict()})

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

    def load_one(raw: dict) -> Dataset | None:
        raw_spec = dict(raw)
        resolved = _resolve(raw_spec, base)
        if resolved is None:
            problems.append(f"Datei nicht gefunden: {raw_spec.get('path', '?')}")
            return None
        raw_spec["path"] = resolved
        spec = ImportSpec.from_dict(raw_spec)
        key = (spec.path, spec.sheet)
        try:
            if key not in tables:
                tables[key] = read_table(spec.path, spec.sheet)
            result = load_datasets(spec, tables[key])
        except LoadError as exc:
            problems.append(f"{Path(spec.path).name}: {exc}")
            return None
        if not result.datasets:
            problems.append(f"{Path(spec.path).name}: keine gültigen Daten mehr in der gewählten Spalte.")
            return None
        return result.datasets[0]

    for entry in data["datasets"]:
        if "members" in entry:
            members = [m for m in (load_one(raw) for raw in entry["members"]) if m is not None]
            try:
                ds = combine_repeats(members, entry.get("name")).dataset
            except ValueError as exc:
                problems.append(f"„{entry.get('name', 'Zusammenfassung')}“: {exc}")
                continue
        else:
            ds = load_one(entry.get("spec", {}))
            if ds is None:
                continue
        ds.apply_style(entry.get("style", {}))
        datasets.append(ds)

    return ProjectData(datasets, settings, problems)
