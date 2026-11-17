"""Tests for the difficulty presets (spec 2.4)."""

from collections import Counter

import numpy as np
import pytest

from exoplanet_lab.generator.presets import (
    GRADED_PRESETS,
    NOISE_PPM_RANGE,
    SPOT_ONLY_ACTIVITY,
    SPOT_ONLY_NOISE_PPM,
    SPOT_ONLY_ROTATION_DAYS,
    STAR_RADIUS,
    TRAP_BINARIES,
    TRAP_PLANETS,
    draw_settings,
    generate_preset_scenario,
)
from exoplanet_lab.generator.scenario import generate_scenario, in_transit_mask
from exoplanet_lab.generator.settings import (
    TRAP_KIND_TYPES,
    Preset,
    ScenarioSettings,
    ScenarioType,
    TrapKind,
)
from exoplanet_lab.generator.timeseries import DOWNLINK_GAP_END, DOWNLINK_GAP_START

GRADED = [Preset.EASY, Preset.MEDIUM, Preset.HARD]
DRAWN = [*GRADED, Preset.TRAP]
N_SEEDS = 300


def settings_for(preset: Preset, n: int = N_SEEDS) -> list[ScenarioSettings]:
    return [draw_settings(preset, seed) for seed in range(n)]


def trap_settings(kind: TrapKind, n: int = 15) -> list[ScenarioSettings]:
    """The first ``n`` Trap seeds that produce ``kind``."""
    found: list[ScenarioSettings] = []
    seed = 0
    while len(found) < n:
        settings = draw_settings(Preset.TRAP, seed)
        if settings.trap_kind is kind:
            found.append(settings)
        seed += 1
    return found


# --- every drawn preset --------------------------------------------------------------------


@pytest.mark.parametrize("preset", DRAWN)
def test_same_seed_gives_same_settings(preset: Preset) -> None:
    assert draw_settings(preset, 11) == draw_settings(preset, 11)
    assert draw_settings(preset, 11) != draw_settings(preset, 12)


@pytest.mark.parametrize("preset", DRAWN)
def test_settings_record_preset_and_seed(preset: Preset) -> None:
    settings = draw_settings(preset, 5)
    assert settings.preset is preset
    assert settings.seed == 5


@pytest.mark.parametrize("preset", DRAWN)
def test_star_radius_and_noise_stay_in_range(preset: Preset) -> None:
    for settings in settings_for(preset, 100):
        assert settings.star.radius_rsun in STAR_RADIUS
        assert NOISE_PPM_RANGE[0] <= settings.observation.noise_ppm <= NOISE_PPM_RANGE[1]


@pytest.mark.parametrize("preset", DRAWN)
def test_preset_scenario_generates(preset: Preset) -> None:
    scenario = generate_preset_scenario(preset, 3)
    assert scenario.answer_key.settings == draw_settings(preset, 3)


def test_custom_preset_has_no_draws() -> None:
    with pytest.raises(ValueError, match="Custom"):
        draw_settings(Preset.CUSTOM, 1)


# --- Easy, Medium, Hard --------------------------------------------------------------------


def test_easy_is_planet_only_without_extra_gaps() -> None:
    for settings in settings_for(Preset.EASY):
        assert settings.type is ScenarioType.PLANET
        assert not settings.observation.extra_gaps


@pytest.mark.parametrize("preset", [Preset.MEDIUM, Preset.HARD])
def test_medium_and_hard_mix_is_about_70_30(preset: Preset) -> None:
    types = Counter(s.type for s in settings_for(preset))
    assert set(types) == {ScenarioType.PLANET, ScenarioType.NO_PLANET}
    # 70 % of 300 is 210; the binomial standard deviation is about 8.
    assert 180 <= types[ScenarioType.PLANET] <= 240


@pytest.mark.parametrize("preset", [Preset.MEDIUM, Preset.HARD])
def test_extra_gaps_appear_about_half_the_time(preset: Preset) -> None:
    with_gaps = sum(s.observation.extra_gaps for s in settings_for(preset))
    assert 120 <= with_gaps <= 180


@pytest.mark.parametrize("preset", GRADED)
def test_planet_values_stay_in_preset_ranges(preset: Preset) -> None:
    ranges = GRADED_PRESETS[preset]
    for settings in settings_for(preset, 100):
        assert settings.star.activity_amplitude in ranges.activity
        assert settings.star.rotation_period_days in ranges.rotation_days
        if settings.planet is not None:
            assert settings.planet.radius_rearth in ranges.radius_rearth
            assert settings.planet.period_days in ranges.period_days
            assert settings.planet.impact_parameter in ranges.impact_parameter


@pytest.mark.parametrize("preset", GRADED)
def test_planets_hit_the_target_snr_with_enough_transits(preset: Preset) -> None:
    ranges = GRADED_PRESETS[preset]
    planets = [s for s in settings_for(preset, 60) if s.type is ScenarioType.PLANET]
    snrs = []
    for settings in planets:
        key = generate_scenario(settings).answer_key
        assert key.planet is not None and key.expected_snr is not None
        assert key.planet.n_transits_observed >= ranges.min_transits
        assert ranges.snr.low - 1e-9 <= key.expected_snr <= ranges.snr.high + 1e-9
        snrs.append(key.expected_snr)
    # The draws should spread over the range, not bunch at one end.
    assert min(snrs) < ranges.snr.low + 0.3 * (ranges.snr.high - ranges.snr.low)
    assert max(snrs) > ranges.snr.high - 0.3 * (ranges.snr.high - ranges.snr.low)


def test_snr_ranges_join_up() -> None:
    hard, medium, easy = (GRADED_PRESETS[p].snr for p in (Preset.HARD, Preset.MEDIUM, Preset.EASY))
    assert hard.high == medium.low
    assert medium.high == easy.low


def test_no_planet_noise_matches_planet_noise() -> None:
    # The phantom planet should make no_planet noise levels look like planet noise levels.
    settings = settings_for(Preset.MEDIUM)
    planet = [s.observation.noise_ppm for s in settings if s.type is ScenarioType.PLANET]
    empty = [s.observation.noise_ppm for s in settings if s.type is ScenarioType.NO_PLANET]
    assert np.median(empty) == pytest.approx(np.median(planet), rel=0.35)


# --- Trap ----------------------------------------------------------------------------------


def test_trap_draws_every_kind_about_equally() -> None:
    kinds = Counter(s.trap_kind for s in settings_for(Preset.TRAP))
    assert set(kinds) == set(TrapKind)
    assert all(25 <= count <= 75 for count in kinds.values())  # 50 expected each


def test_trap_kind_matches_type() -> None:
    for settings in settings_for(Preset.TRAP, 100):
        assert settings.trap_kind is not None
        assert settings.type is TRAP_KIND_TYPES[settings.trap_kind]


def test_spot_only_is_a_very_active_quiet_star() -> None:
    for settings in trap_settings(TrapKind.SPOT_ONLY):
        assert settings.planet is None and settings.binary is None
        assert settings.star.activity_amplitude in SPOT_ONLY_ACTIVITY
        assert settings.star.rotation_period_days in SPOT_ONLY_ROTATION_DAYS
        assert settings.observation.noise_ppm in SPOT_ONLY_NOISE_PPM


@pytest.mark.parametrize("kind", [TrapKind.NEAR_EQUAL_EB, TrapKind.CLASSIC_EB])
def test_binary_traps_have_their_depths_and_two_eclipses(kind: TrapKind) -> None:
    primary_range, ratio_range = TRAP_BINARIES[kind]
    for settings in trap_settings(kind, 8):
        binary = settings.binary
        assert binary is not None
        assert binary.primary_depth in primary_range
        assert binary.secondary_ratio in ratio_range
        scenario = generate_scenario(settings)
        key_binary = scenario.answer_key.binary
        assert key_binary is not None
        assert 1 - scenario.model_flux.min() == pytest.approx(binary.primary_depth, rel=0.02)


def test_grazing_planet_is_grazing() -> None:
    ranges = TRAP_PLANETS[TrapKind.GRAZING_PLANET]
    for settings in trap_settings(TrapKind.GRAZING_PLANET, 8):
        key = generate_scenario(settings).answer_key
        assert key.planet is not None and key.expected_snr is not None
        assert key.planet.impact_parameter >= 0.9
        assert key.planet.n_transits_observed >= 2
        assert ranges.snr.low - 1e-9 <= key.expected_snr <= ranges.snr.high + 1e-9


def test_two_transit_has_exactly_two_transits() -> None:
    for settings in trap_settings(TrapKind.TWO_TRANSIT, 8):
        key = generate_scenario(settings).answer_key
        assert key.planet is not None
        assert key.planet.n_transits_observed == 2
        assert key.planet.period_days >= 9.0


def test_alias_gap_hides_the_middle_of_three_transits() -> None:
    for settings in trap_settings(TrapKind.ALIAS_GAP, 8):
        scenario = generate_scenario(settings)
        planet = scenario.answer_key.planet
        assert planet is not None
        assert planet.n_transits_observed == 2
        middle = planet.t0_days + planet.period_days
        half = planet.duration_days / 2
        assert DOWNLINK_GAP_START <= middle - half and middle + half <= DOWNLINK_GAP_END
        # No fourth transit inside the sector, and no data at all from the middle one.
        assert planet.t0_days - planet.period_days + half < 0
        near_middle = in_transit_mask(
            scenario.time,
            period_days=1e6,  # one window only
            t0_days=middle,
            duration_days=planet.duration_days,
        )
        assert not near_middle.any()
