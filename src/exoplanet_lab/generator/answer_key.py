"""The answer key: the hidden truth saved with every scenario (spec 2.5).

The key holds the full settings (enough to rebuild the scenario) plus the derived true values a
pipeline is scored against. Blind mode, which hides the key until a result is submitted, is
handled by the app; this module only describes the data.
"""

import hashlib

from pydantic import BaseModel, ConfigDict, Field

from exoplanet_lab.generator.settings import Preset, ScenarioSettings, ScenarioType, TrapKind
from exoplanet_lab.generator.timeseries import Gap

SCENARIO_ID_LENGTH = 12
"""Number of hex characters in a scenario ID."""


class _FrozenRecord(BaseModel):
    """Base for answer-key records: immutable, no unknown fields."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class StarTruth(_FrozenRecord):
    """True properties of the host (or primary) star and of the observation noise."""

    radius_rsun: float
    mass_msun: float
    teff_k: float = Field(description="Temperature used to pick the limb-darkening coefficients.")
    limb_darkening_u1: float
    limb_darkening_u2: float
    noise_ppm: float = Field(description="White noise per point, before median normalization.")
    activity_amplitude: float
    rotation_period_days: float


class PlanetTruth(_FrozenRecord):
    """True properties of the transiting planet."""

    period_days: float
    t0_days: float = Field(description="First mid-transit time at or after the start of data.")
    duration_days: float = Field(description="Total transit duration T14.")
    depth: float = Field(
        description="Noise-free model dip at mid-transit, limb darkening included."
    )
    radius_ratio: float = Field(description="Rₚ/R★.")
    radius_rearth: float
    a_over_rstar: float
    impact_parameter: float
    inclination_deg: float
    n_transits_observed: int = Field(
        description="Transits with at least half of their in-transit points outside the gaps."
    )
    n_in_transit_points: int = Field(description="Observed points inside any transit window.")


class BinaryTruth(_FrozenRecord):
    """True properties of an eclipsing binary."""

    period_days: float = Field(description="True orbital period (not the half-period alias).")
    t0_days: float = Field(description="First mid-primary-eclipse time.")
    primary_depth: float
    secondary_depth: float
    radius_ratio: float = Field(description="Companion radius over primary radius.")
    a_over_rstar: float
    impact_parameter: float
    companion_mass_msun: float


class AnswerKey(_FrozenRecord):
    """Everything a scenario's result is scored against."""

    scenario_id: str
    seed: int
    preset: Preset
    type: ScenarioType
    has_planet: bool
    trap_kind: TrapKind | None
    expected_snr: float | None = Field(
        description="depth ÷ noise per point × √(observed in-transit points); white noise only. "
        "None when there is no planet."
    )
    star: StarTruth
    planet: PlanetTruth | None
    binary: BinaryTruth | None
    gaps: tuple[Gap, ...] = Field(description="Data gaps as (start, end) in days.")
    settings: ScenarioSettings = Field(description="The full settings; enough to rebuild it.")


def scenario_id(settings: ScenarioSettings) -> str:
    """A short, stable ID for a scenario: the start of a SHA-256 hash of its settings.

    Identical settings always give the same ID, and any change to a setting gives a new one.
    """
    digest = hashlib.sha256(settings.model_dump_json().encode("utf-8")).hexdigest()
    return digest[:SCENARIO_ID_LENGTH]
