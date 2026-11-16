"""Synthetic light-curve generator (spec sections 2.1-2.6).

Turns a fully specified :class:`ScenarioSettings` (or a preset plus a seed) into a TESS-like
light curve and its answer key.
"""

from exoplanet_lab.generator.settings import (
    BinarySettings,
    ObservationSettings,
    PlanetSettings,
    Preset,
    ScenarioSettings,
    ScenarioType,
    StarSettings,
    TrapKind,
)

__all__ = [
    "BinarySettings",
    "ObservationSettings",
    "PlanetSettings",
    "Preset",
    "ScenarioSettings",
    "ScenarioType",
    "StarSettings",
    "TrapKind",
]
