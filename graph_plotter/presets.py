"""Vorlagen: Schriftgrößen und Exportgröße für typische Einsatzzwecke."""

from __future__ import annotations

from dataclasses import dataclass

from .plotting import PlotSettings


@dataclass(frozen=True)
class Preset:
    name: str
    label_fontsize: float
    tick_fontsize: float
    legend_fontsize: float
    width_cm: float
    height_cm: float


PRESETS = {
    "screen": Preset("Bildschirm", 14, 12, 12, 16.0, 10.0),
    "paper1": Preset("Paper, einspaltig (8,5 cm)", 9, 8, 7, 8.5, 6.5),
    "paper2": Preset("Paper, zweispaltig (17 cm)", 10, 9, 8, 17.0, 10.0),
    "thesis": Preset("Abschlussarbeit (15 cm)", 11, 10, 9, 15.0, 9.5),
    "slides": Preset("Präsentation 16:9", 20, 16, 16, 25.4, 14.3),
}


def apply_preset(settings: PlotSettings, key: str) -> None:
    preset = PRESETS[key]
    settings.label_fontsize = preset.label_fontsize
    settings.tick_fontsize = preset.tick_fontsize
    settings.legend_fontsize = preset.legend_fontsize
    settings.export.width_cm = preset.width_cm
    settings.export.height_cm = preset.height_cm


def matching_preset(settings: PlotSettings) -> str | None:
    """Schlüssel der Vorlage, die exakt zu den Einstellungen passt (sonst None)."""
    for key, p in PRESETS.items():
        if (settings.label_fontsize, settings.tick_fontsize, settings.legend_fontsize,
                settings.export.width_cm, settings.export.height_cm) == (
                p.label_fontsize, p.tick_fontsize, p.legend_fontsize, p.width_cm, p.height_cm):
            return key
    return None
