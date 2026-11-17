"""Synthetic light-curve generator (spec sections 2.1-2.6).

Turns a fully specified :class:`ScenarioSettings` (or a preset plus a seed) into a TESS-like
light curve and its answer key.
"""

from exoplanet_lab.generator.answer_key import AnswerKey
from exoplanet_lab.generator.scenario import Scenario, generate_scenario
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
    "AnswerKey",
    "BinarySettings",
    "ObservationSettings",
    "PlanetSettings",
    "Preset",
    "Scenario",
    "ScenarioSettings",
    "ScenarioType",
    "StarSettings",
    "TrapKind",
    "generate_scenario",
]
