"""Tests for scenario assembly and the answer key."""

from typing import Any

import numpy as np
import pytest

from exoplanet_lab.generator.answer_key import SCENARIO_ID_LENGTH, AnswerKey, scenario_id
from exoplanet_lab.generator.physics import stellar_mass_from_radius
from exoplanet_lab.generator.scenario import (
    count_observed_transits,
    expected_snr,
    generate_scenario,
    in_transit_mask,
)
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
from exoplanet_lab.generator.timeseries import (
    DOWNLINK_GAP_END,
    DOWNLINK_GAP_START,
    full_time_grid,
    observed_mask,
)

QUIET_STAR = StarSettings(radius_rsun=1.0, activity_amplitude=0.0, rotation_period_days=10.0)
PLANET = PlanetSettings(radius_rearth=10.0, period_days=3.0, t0_days=1.0, impact_parameter=0.0)
BINARY = BinarySettings(
    period_days=4.0, t0_days=0.5, primary_depth=0.1, secondary_ratio=0.5, impact_parameter=0.2
)

TIME = full_time_grid()
DOWNLINK_ONLY = observed_mask(TIME, ((DOWNLINK_GAP_START, DOWNLINK_GAP_END),))


def make_settings(
    *, noise_ppm: float = 500.0, extra_gaps: bool = False, **overrides: Any
) -> ScenarioSettings:
    """A valid Custom planet scenario on a quiet star, with fields replaced by ``overrides``."""
    fields: dict[str, Any] = {
        "seed": 42,
        "preset": Preset.CUSTOM,
        "type": ScenarioType.PLANET,
        "star": QUIET_STAR,
        "observation": ObservationSettings(noise_ppm=noise_ppm, extra_gaps=extra_gaps),
        "planet": PLANET,
    }
    fields.update(overrides)
    return ScenarioSettings(**fields)


# --- transit counting ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("t0", "expected"),
    [
        (1.7, 4),  # 1.7, 7.7, 19.7, 25.7; the transit at 13.7 is entirely in the downlink gap
        (1.0, 5),  # the transit at 13.0 has 0.7 of its 1-day window before the gap: counted
        (1.4, 4),  # the transit at 13.4 has only 0.3 before the gap: not counted
        (3.3, 5),  # the last transit at 27.3 is 0.6 inside the sector: counted
        (3.7, 4),  # the last transit at 27.7 is only 0.2 inside the sector: not counted
    ],
)
def test_count_observed_transits_uses_half_rule(t0: float, expected: int) -> None:
    count = count_observed_transits(
        TIME, DOWNLINK_ONLY, period_days=6.0, t0_days=t0, duration_days=1.0
    )
    assert count == expected


def test_transit_cut_by_sector_start_follows_half_rule() -> None:
    # Period 6 from t0 = 0.3: the transit before t0 (at -5.7) is outside the data entirely, and
    # the one at 0.3 has 0.8 of its window inside: counted. Mids 0.3, 6.3, 12.3, 18.3, 24.3.
    count = count_observed_transits(
        TIME, DOWNLINK_ONLY, period_days=6.0, t0_days=0.3, duration_days=1.0
    )
    assert count == 5


def test_in_transit_mask_covers_one_duration_per_transit() -> None:
    mask = in_transit_mask(TIME, period_days=6.0, t0_days=3.2, duration_days=0.5)
    # Transits at 3.2, 9.2, 15.2, 21.2, 27.2; the last window (26.95-27.45) is cut by the end
    # of the sector at 27.4, leaving 0.45 days of it.
    assert mask.sum() == pytest.approx((4 * 0.5 + 0.45) * 720, abs=6)


# --- reproducibility -----------------------------------------------------------------------


def test_same_settings_give_identical_scenarios() -> None:
    settings = make_settings(extra_gaps=True)
    first, second = generate_scenario(settings), generate_scenario(settings)
    np.testing.assert_array_equal(first.time, second.time)
    np.testing.assert_array_equal(first.flux, second.flux)
    assert first.answer_key == second.answer_key


def test_different_seeds_give_different_noise() -> None:
    first = generate_scenario(make_settings(seed=1))
    second = generate_scenario(make_settings(seed=2))
    assert not np.array_equal(first.flux, second.flux)
    assert first.answer_key.scenario_id != second.answer_key.scenario_id


def test_extra_gaps_do_not_change_remaining_points() -> None:
    without = generate_scenario(make_settings(extra_gaps=False))
    with_gaps = generate_scenario(make_settings(extra_gaps=True))
    assert with_gaps.time.size < without.time.size
    kept = np.isin(without.time, with_gaps.time)
    # Same raw values, up to the single factor from re-normalizing the median.
    ratio = with_gaps.flux / without.flux[kept]
    np.testing.assert_allclose(ratio, ratio[0], rtol=1e-12)


# --- light curve ---------------------------------------------------------------------------


def test_arrays_line_up_and_skip_gaps() -> None:
    scenario = generate_scenario(make_settings())
    n = scenario.time.size
    assert scenario.flux.size == scenario.flux_err.size == scenario.model_flux.size == n
    assert n == int(DOWNLINK_ONLY.sum())
    in_gap = (scenario.time >= DOWNLINK_GAP_START) & (scenario.time < DOWNLINK_GAP_END)
    assert not in_gap.any()


def test_flux_is_normalized_and_errors_match_noise() -> None:
    scenario = generate_scenario(make_settings(noise_ppm=800.0))
    assert np.median(scenario.flux) == pytest.approx(1.0, abs=1e-12)
    assert np.all(scenario.flux_err == scenario.flux_err[0])
    assert scenario.flux_err[0] == pytest.approx(800e-6, rel=1e-3)
    residuals = scenario.flux - scenario.model_flux
    assert np.std(residuals) == pytest.approx(800e-6, rel=0.03)


def test_in_transit_flux_dips_by_the_true_depth() -> None:
    scenario = generate_scenario(make_settings(noise_ppm=300.0))
    planet = scenario.answer_key.planet
    assert planet is not None
    # The central fifth of each transit is close to the full depth for b = 0.
    core = in_transit_mask(
        scenario.time,
        period_days=planet.period_days,
        t0_days=planet.t0_days,
        duration_days=planet.duration_days / 5,
    )
    measured_depth = 1.0 - scenario.flux[core].mean()
    assert measured_depth == pytest.approx(planet.depth, rel=0.05)


def test_starspots_are_added_to_the_flux() -> None:
    spotty = StarSettings(radius_rsun=1.0, activity_amplitude=0.01, rotation_period_days=4.0)
    scenario = generate_scenario(make_settings(star=spotty, noise_ppm=100.0))
    trend = scenario.flux - scenario.model_flux
    assert np.ptp(trend) == pytest.approx(0.01, rel=0.15)


# --- answer key: planet --------------------------------------------------------------------


def test_planet_answer_key() -> None:
    settings = make_settings(noise_ppm=500.0)
    key = generate_scenario(settings).answer_key
    assert key.type is ScenarioType.PLANET
    assert key.has_planet
    assert key.binary is None
    assert key.trap_kind is None
    assert key.settings == settings
    assert key.seed == 42
    assert key.preset is Preset.CUSTOM
    assert key.gaps == ((DOWNLINK_GAP_START, DOWNLINK_GAP_END),)

    planet = key.planet
    assert planet is not None
    assert planet.period_days == 3.0
    assert planet.t0_days == 1.0
    assert planet.radius_rearth == 10.0
    assert planet.n_transits_observed == 9  # 1, 4, ..., 25; none touch the gap (13.2-14.2)
    assert 0 < planet.duration_days < 0.2
    assert planet.depth > planet.radius_ratio**2  # central transit: limb darkening deepens it

    star = key.star
    assert star.mass_msun == pytest.approx(stellar_mass_from_radius(1.0))
    assert star.noise_ppm == 500.0


def test_expected_snr_matches_formula() -> None:
    scenario = generate_scenario(make_settings(noise_ppm=500.0))
    key = scenario.answer_key
    planet = key.planet
    assert planet is not None and key.expected_snr is not None
    in_transit = in_transit_mask(
        scenario.time,
        period_days=planet.period_days,
        t0_days=planet.t0_days,
        duration_days=planet.duration_days,
    )
    assert planet.n_in_transit_points == in_transit.sum()
    expected = planet.depth / 500e-6 * np.sqrt(in_transit.sum())
    assert key.expected_snr == pytest.approx(expected)
    assert expected_snr(planet.depth, 500.0, planet.n_in_transit_points) == key.expected_snr


def test_expected_snr_falls_with_noise() -> None:
    quiet = generate_scenario(make_settings(noise_ppm=200.0)).answer_key.expected_snr
    noisy = generate_scenario(make_settings(noise_ppm=800.0)).answer_key.expected_snr
    assert quiet is not None and noisy is not None
    assert quiet == pytest.approx(4 * noisy)


def test_too_few_observed_transits_is_rejected() -> None:
    # Transits at 13.4 (in the downlink gap) and 26.9: only one observed.
    planet = PlanetSettings(radius_rearth=5.0, period_days=13.5, t0_days=13.4, impact_parameter=0)
    with pytest.raises(ValueError, match="transit"):
        generate_scenario(make_settings(planet=planet))


def test_planet_that_misses_the_star_is_rejected() -> None:
    planet = PlanetSettings(radius_rearth=0.8, period_days=3.0, t0_days=1.0, impact_parameter=1.05)
    settings = make_settings(preset=Preset.TRAP, trap_kind=TrapKind.GRAZING_PLANET, planet=planet)
    with pytest.raises(ValueError, match="misses"):
        generate_scenario(settings)


# --- answer key: no planet and eclipsing binary --------------------------------------------


def test_no_planet_answer_key() -> None:
    settings = make_settings(type=ScenarioType.NO_PLANET, planet=None)
    scenario = generate_scenario(settings)
    key = scenario.answer_key
    assert not key.has_planet
    assert key.planet is None and key.binary is None
    assert key.expected_snr is None
    assert np.all(scenario.model_flux == 1.0)


def test_eclipsing_binary_answer_key() -> None:
    settings = make_settings(type=ScenarioType.ECLIPSING_BINARY, planet=None, binary=BINARY)
    scenario = generate_scenario(settings)
    key = scenario.answer_key
    assert not key.has_planet
    assert key.planet is None
    assert key.expected_snr is None
    binary = key.binary
    assert binary is not None
    assert binary.period_days == 4.0
    assert binary.primary_depth == pytest.approx(0.1)
    assert binary.secondary_depth == pytest.approx(0.05)
    assert 1 - scenario.model_flux.min() == pytest.approx(0.1, rel=1e-3)


def test_trap_kind_is_recorded() -> None:
    settings = make_settings(
        preset=Preset.TRAP,
        trap_kind=TrapKind.CLASSIC_EB,
        type=ScenarioType.ECLIPSING_BINARY,
        planet=None,
        binary=BINARY,
    )
    assert generate_scenario(settings).answer_key.trap_kind is TrapKind.CLASSIC_EB


# --- answer key: ID and serialization ------------------------------------------------------


def test_scenario_id_is_stable_and_short() -> None:
    settings = make_settings()
    assert scenario_id(settings) == scenario_id(make_settings())
    assert len(scenario_id(settings)) == SCENARIO_ID_LENGTH
    assert scenario_id(settings) != scenario_id(make_settings(noise_ppm=501.0))


def test_answer_key_round_trips_through_json() -> None:
    key = generate_scenario(make_settings(extra_gaps=True)).answer_key
    assert AnswerKey.model_validate_json(key.model_dump_json()) == key
