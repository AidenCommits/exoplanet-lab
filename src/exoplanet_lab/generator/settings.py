"""Generator settings: validated, immutable descriptions of one scenario.

A :class:`ScenarioSettings` holds every value the generator needs. Given the same settings the
generator always produces the same light curve, so these settings (saved in the answer key) are
enough to rebuild any scenario. Ranges follow spec section 2.3; preset and Trap rules follow
section 2.4.

Rules that need the time grid (for example "at least 3 transits land on real data") cannot be
checked here; the generator checks them when it builds the light curve.
"""

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

MAX_SEED = 2**32 - 1
"""Largest allowed seed. Keeps seeds exact in JSON and in JavaScript (the frontend)."""

MAX_IMPACT_PARAMETER = 0.9
"""Largest impact parameter outside the Trap preset (spec 2.3)."""

MAX_TRAP_IMPACT_PARAMETER = 1.05
"""Largest impact parameter in the Trap preset, which allows grazing transits."""


class ScenarioType(StrEnum):
    """What the light curve really contains (spec 2.1)."""

    PLANET = "planet"
    NO_PLANET = "no_planet"
    ECLIPSING_BINARY = "eclipsing_binary"


class Preset(StrEnum):
    """Difficulty presets (spec 2.4). ``CUSTOM`` means every value was set by hand."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    TRAP = "trap"
    CUSTOM = "custom"


class TrapKind(StrEnum):
    """The six kinds of Trap scenario (spec 2.4)."""

    NEAR_EQUAL_EB = "near_equal_eb"
    SPOT_ONLY = "spot_only"
    GRAZING_PLANET = "grazing_planet"
    TWO_TRANSIT = "two_transit"
    ALIAS_GAP = "alias_gap"
    CLASSIC_EB = "classic_eb"


TRAP_KIND_TYPES: dict[TrapKind, ScenarioType] = {
    TrapKind.NEAR_EQUAL_EB: ScenarioType.ECLIPSING_BINARY,
    TrapKind.SPOT_ONLY: ScenarioType.NO_PLANET,
    TrapKind.GRAZING_PLANET: ScenarioType.PLANET,
    TrapKind.TWO_TRANSIT: ScenarioType.PLANET,
    TrapKind.ALIAS_GAP: ScenarioType.PLANET,
    TrapKind.CLASSIC_EB: ScenarioType.ECLIPSING_BINARY,
}
"""The scenario type each Trap kind produces."""

PRESET_TYPES: dict[Preset, frozenset[ScenarioType]] = {
    Preset.EASY: frozenset({ScenarioType.PLANET}),
    Preset.MEDIUM: frozenset({ScenarioType.PLANET, ScenarioType.NO_PLANET}),
    Preset.HARD: frozenset({ScenarioType.PLANET, ScenarioType.NO_PLANET}),
    Preset.TRAP: frozenset(ScenarioType),
    Preset.CUSTOM: frozenset(ScenarioType),
}
"""The scenario types each preset may produce."""


class _FrozenModel(BaseModel):
    """Base for all settings: immutable, no unknown fields, no NaN or infinity."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)


class StarSettings(_FrozenModel):
    """The host star (the primary star for an eclipsing binary)."""

    radius_rsun: float = Field(ge=0.5, le=1.5, description="Star radius in solar radii.")
    activity_amplitude: float = Field(
        ge=0.0,
        le=0.02,
        description="Peak-to-peak starspot variability as a fraction of the flux (0.01 = 1 %).",
    )
    rotation_period_days: float = Field(
        ge=1.0, le=15.0, description="Star rotation period; the spot signal repeats at this period."
    )


class PlanetSettings(_FrozenModel):
    """One transiting planet on a circular orbit."""

    radius_rearth: float = Field(ge=0.8, le=15.0, description="Planet radius in Earth radii.")
    period_days: float = Field(ge=0.5, le=13.5, description="Orbital period in days.")
    t0_days: float = Field(
        ge=0.0, description="First mid-transit time at or after the start of the data, in days."
    )
    impact_parameter: float = Field(
        ge=0.0,
        le=MAX_TRAP_IMPACT_PARAMETER,
        description="Sky-projected distance of the transit chord from the star's centre, "
        "in star radii. Above 0.9 is allowed only in the Trap preset.",
    )

    @model_validator(mode="after")
    def _t0_within_first_period(self) -> Self:
        if self.t0_days >= self.period_days:
            raise ValueError("t0_days must be less than period_days (it is the first transit)")
        return self


class BinarySettings(_FrozenModel):
    """Two stars eclipsing each other, with the secondary eclipse at phase 0.5."""

    period_days: float = Field(ge=0.5, le=13.5, description="True orbital period in days.")
    t0_days: float = Field(ge=0.0, description="First mid-primary-eclipse time, in days.")
    primary_depth: float = Field(
        ge=0.01, le=0.30, description="Depth of the primary eclipse as a fraction of the flux."
    )
    secondary_ratio: float = Field(
        ge=0.0, le=1.0, description="Secondary eclipse depth divided by the primary depth."
    )
    impact_parameter: float = Field(
        ge=0.0, le=MAX_IMPACT_PARAMETER, description="Impact parameter of the primary eclipse."
    )

    @model_validator(mode="after")
    def _t0_within_first_period(self) -> Self:
        if self.t0_days >= self.period_days:
            raise ValueError("t0_days must be less than period_days (it is the first eclipse)")
        return self


class ObservationSettings(_FrozenModel):
    """How the star was observed: noise level and data gaps."""

    noise_ppm: float = Field(
        ge=100.0, le=3000.0, description="White noise per 2-minute point, in parts per million."
    )
    extra_gaps: bool = Field(
        description="Add random data gaps on top of the mid-sector downlink gap."
    )


class ScenarioSettings(_FrozenModel):
    """Everything needed to generate one scenario, reproducibly.

    Exactly one of ``planet`` and ``binary`` is set for the ``planet`` and ``eclipsing_binary``
    types; both are ``None`` for ``no_planet``.
    """

    seed: int = Field(ge=0, le=MAX_SEED, description="Seed for every random draw.")
    preset: Preset
    type: ScenarioType
    trap_kind: TrapKind | None = Field(
        default=None, description="Which Trap kind produced this scenario; None outside Trap."
    )
    star: StarSettings
    observation: ObservationSettings
    planet: PlanetSettings | None = None
    binary: BinarySettings | None = None

    @model_validator(mode="after")
    def _components_match_type(self) -> Self:
        has_planet = self.planet is not None
        has_binary = self.binary is not None
        expected = {
            ScenarioType.PLANET: (True, False),
            ScenarioType.NO_PLANET: (False, False),
            ScenarioType.ECLIPSING_BINARY: (False, True),
        }[self.type]
        if (has_planet, has_binary) != expected:
            raise ValueError(
                f"type {self.type.value!r} needs planet={'set' if expected[0] else 'None'} "
                f"and binary={'set' if expected[1] else 'None'}"
            )
        return self

    @model_validator(mode="after")
    def _type_allowed_by_preset(self) -> Self:
        if self.type not in PRESET_TYPES[self.preset]:
            raise ValueError(
                f"preset {self.preset.value!r} cannot produce type {self.type.value!r}"
            )
        return self

    @model_validator(mode="after")
    def _trap_kind_consistent(self) -> Self:
        if self.preset is Preset.TRAP:
            if self.trap_kind is None:
                raise ValueError("the Trap preset needs a trap_kind")
            if TRAP_KIND_TYPES[self.trap_kind] is not self.type:
                raise ValueError(
                    f"trap_kind {self.trap_kind.value!r} produces type "
                    f"{TRAP_KIND_TYPES[self.trap_kind].value!r}, not {self.type.value!r}"
                )
        elif self.trap_kind is not None:
            raise ValueError("trap_kind is only allowed with the Trap preset")
        return self

    @model_validator(mode="after")
    def _grazing_only_in_trap(self) -> Self:
        if (
            self.planet is not None
            and self.planet.impact_parameter > MAX_IMPACT_PARAMETER
            and self.preset is not Preset.TRAP
        ):
            raise ValueError(
                f"impact_parameter above {MAX_IMPACT_PARAMETER} is only allowed in the Trap preset"
            )
        return self
