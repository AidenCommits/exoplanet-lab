"""Tests for the generator settings models (spec 2.3 ranges, 2.4 preset and Trap rules)."""

from typing import Any

import pytest
from pydantic import ValidationError

from exoplanet_lab.generator.settings import (
    MAX_SEED,
    TRAP_KIND_TYPES,
    BinarySettings,
    ObservationSettings,
    PlanetSettings,
    Preset,
    ScenarioSettings,
    ScenarioType,
    StarSettings,
    TrapKind,
)

STAR = StarSettings(radius_rsun=1.0, activity_amplitude=0.001, rotation_period_days=10.0)
OBSERVATION = ObservationSettings(noise_ppm=500.0, extra_gaps=False)
PLANET = PlanetSettings(radius_rearth=10.0, period_days=3.0, t0_days=1.2, impact_parameter=0.3)
BINARY = BinarySettings(
    period_days=4.0, t0_days=0.5, primary_depth=0.1, secondary_ratio=0.5, impact_parameter=0.2
)


def make_settings(**overrides: Any) -> ScenarioSettings:
    """A valid Custom planet scenario, with any fields replaced by ``overrides``."""
    fields: dict[str, Any] = {
        "seed": 42,
        "preset": Preset.CUSTOM,
        "type": ScenarioType.PLANET,
        "star": STAR,
        "observation": OBSERVATION,
        "planet": PLANET,
    }
    fields.update(overrides)
    return ScenarioSettings(**fields)


# --- valid scenarios ---------------------------------------------------------------------


def test_valid_planet_scenario() -> None:
    settings = make_settings()
    assert settings.type is ScenarioType.PLANET
    assert settings.binary is None
    assert settings.trap_kind is None


def test_valid_no_planet_scenario() -> None:
    settings = make_settings(type=ScenarioType.NO_PLANET, planet=None)
    assert settings.planet is None and settings.binary is None


def test_valid_eclipsing_binary_scenario() -> None:
    settings = make_settings(type=ScenarioType.ECLIPSING_BINARY, planet=None, binary=BINARY)
    assert settings.binary == BINARY


@pytest.mark.parametrize("seed", [0, MAX_SEED])
def test_seed_bounds_accepted(seed: int) -> None:
    assert make_settings(seed=seed).seed == seed


# --- ranges from spec 2.3 ----------------------------------------------------------------


@pytest.mark.parametrize("seed", [-1, MAX_SEED + 1])
def test_seed_out_of_range_rejected(seed: int) -> None:
    with pytest.raises(ValidationError):
        make_settings(seed=seed)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("radius_rsun", 0.49),
        ("radius_rsun", 1.51),
        ("activity_amplitude", -0.001),
        ("activity_amplitude", 0.021),
        ("rotation_period_days", 0.9),
        ("rotation_period_days", 15.1),
        ("radius_rsun", float("nan")),
    ],
)
def test_star_out_of_range_rejected(field: str, value: float) -> None:
    with pytest.raises(ValidationError):
        StarSettings(**{**STAR.model_dump(), field: value})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("radius_rearth", 0.79),
        ("radius_rearth", 15.1),
        ("period_days", 0.49),
        ("period_days", 13.6),
        ("t0_days", -0.1),
        ("impact_parameter", -0.01),
        ("impact_parameter", 1.06),
    ],
)
def test_planet_out_of_range_rejected(field: str, value: float) -> None:
    with pytest.raises(ValidationError):
        PlanetSettings(**{**PLANET.model_dump(), field: value})


def test_planet_t0_must_be_inside_first_period() -> None:
    with pytest.raises(ValidationError, match="t0_days"):
        PlanetSettings(**{**PLANET.model_dump(), "t0_days": PLANET.period_days})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("primary_depth", 0.009),
        ("primary_depth", 0.31),
        ("secondary_ratio", -0.01),
        ("secondary_ratio", 1.01),
        ("impact_parameter", 0.91),
        ("t0_days", 4.0),
    ],
)
def test_binary_out_of_range_rejected(field: str, value: float) -> None:
    with pytest.raises(ValidationError):
        BinarySettings(**{**BINARY.model_dump(), field: value})


@pytest.mark.parametrize("noise_ppm", [99.0, 3001.0, float("inf")])
def test_noise_out_of_range_rejected(noise_ppm: float) -> None:
    with pytest.raises(ValidationError):
        ObservationSettings(noise_ppm=noise_ppm, extra_gaps=False)


# --- the planet/binary blocks must match the type ----------------------------------------


@pytest.mark.parametrize(
    ("scenario_type", "planet", "binary"),
    [
        (ScenarioType.PLANET, None, None),
        (ScenarioType.PLANET, PLANET, BINARY),
        (ScenarioType.NO_PLANET, PLANET, None),
        (ScenarioType.NO_PLANET, None, BINARY),
        (ScenarioType.ECLIPSING_BINARY, None, None),
        (ScenarioType.ECLIPSING_BINARY, PLANET, None),
    ],
)
def test_components_must_match_type(
    scenario_type: ScenarioType, planet: PlanetSettings | None, binary: BinarySettings | None
) -> None:
    with pytest.raises(ValidationError, match="needs planet="):
        make_settings(type=scenario_type, planet=planet, binary=binary)


# --- preset and Trap rules from spec 2.4 -------------------------------------------------


@pytest.mark.parametrize(
    ("preset", "scenario_type", "planet", "binary"),
    [
        (Preset.EASY, ScenarioType.NO_PLANET, None, None),
        (Preset.EASY, ScenarioType.ECLIPSING_BINARY, None, BINARY),
        (Preset.MEDIUM, ScenarioType.ECLIPSING_BINARY, None, BINARY),
        (Preset.HARD, ScenarioType.ECLIPSING_BINARY, None, BINARY),
    ],
)
def test_preset_rejects_types_outside_its_mix(
    preset: Preset,
    scenario_type: ScenarioType,
    planet: PlanetSettings | None,
    binary: BinarySettings | None,
) -> None:
    with pytest.raises(ValidationError, match="cannot produce"):
        make_settings(preset=preset, type=scenario_type, planet=planet, binary=binary)


@pytest.mark.parametrize("preset", [Preset.MEDIUM, Preset.HARD])
def test_medium_and_hard_allow_no_planet(preset: Preset) -> None:
    assert make_settings(preset=preset, type=ScenarioType.NO_PLANET, planet=None).preset is preset


def test_trap_requires_trap_kind() -> None:
    with pytest.raises(ValidationError, match="needs a trap_kind"):
        make_settings(preset=Preset.TRAP)


def test_trap_kind_rejected_outside_trap() -> None:
    with pytest.raises(ValidationError, match="only allowed with the Trap preset"):
        make_settings(trap_kind=TrapKind.TWO_TRANSIT)


@pytest.mark.parametrize("trap_kind", list(TrapKind))
def test_every_trap_kind_accepted_with_its_type(trap_kind: TrapKind) -> None:
    scenario_type = TRAP_KIND_TYPES[trap_kind]
    settings = make_settings(
        preset=Preset.TRAP,
        trap_kind=trap_kind,
        type=scenario_type,
        planet=PLANET if scenario_type is ScenarioType.PLANET else None,
        binary=BINARY if scenario_type is ScenarioType.ECLIPSING_BINARY else None,
    )
    assert settings.trap_kind is trap_kind


def test_trap_kind_must_match_type() -> None:
    with pytest.raises(ValidationError, match="produces type"):
        make_settings(preset=Preset.TRAP, trap_kind=TrapKind.SPOT_ONLY)


def test_every_trap_kind_has_a_type() -> None:
    assert set(TRAP_KIND_TYPES) == set(TrapKind)


def test_grazing_impact_parameter_only_in_trap() -> None:
    grazing = PlanetSettings(**{**PLANET.model_dump(), "impact_parameter": 1.0})
    with pytest.raises(ValidationError, match="only allowed in the Trap preset"):
        make_settings(planet=grazing)
    trap = make_settings(preset=Preset.TRAP, trap_kind=TrapKind.GRAZING_PLANET, planet=grazing)
    assert trap.planet is not None and trap.planet.impact_parameter == 1.0


# --- immutability and serialisation ------------------------------------------------------


def test_settings_are_frozen() -> None:
    settings = make_settings()
    with pytest.raises(ValidationError):
        settings.seed = 7  # type: ignore[misc]


def test_unknown_fields_rejected() -> None:
    with pytest.raises(ValidationError):
        make_settings(colour="blue")


@pytest.mark.parametrize(
    "settings",
    [
        make_settings(),
        make_settings(type=ScenarioType.NO_PLANET, planet=None),
        make_settings(
            preset=Preset.TRAP,
            trap_kind=TrapKind.NEAR_EQUAL_EB,
            type=ScenarioType.ECLIPSING_BINARY,
            planet=None,
            binary=BINARY,
        ),
    ],
)
def test_json_round_trip(settings: ScenarioSettings) -> None:
    restored = ScenarioSettings.model_validate_json(settings.model_dump_json())
    assert restored == settings
