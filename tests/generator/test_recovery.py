"""Recovery tests: can a planted transit be found again in the generated data? (spec section 6)

These check the generator, not the owner's pipeline, in two ways (decisions log, entry 10):

(a) Direct check: fold at the true period and t0, and compare the measured dip with the true
    model. Uses no search at all, so it tests that the generator put the right signal in.
(b) Search check: run astropy's ``BoxLeastSquares`` with its default period grid and check that
    the strongest peak is within 1 % of the true period.

Medium and Hard stars have starspots far stronger than their transits, and removing those is the
pipeline's detrending job. So for them these tests generate the same scenario with activity set
to 0. Every random part of the generator has its own random stream, so this changes nothing
else: the noise, gaps and transits are identical.
"""

import numpy as np
import pytest
from astropy.timeseries import BoxLeastSquares

from exoplanet_lab.generator.presets import draw_settings
from exoplanet_lab.generator.scenario import Scenario, generate_scenario, in_transit_mask
from exoplanet_lab.generator.settings import (
    ObservationSettings,
    PlanetSettings,
    Preset,
    ScenarioSettings,
    ScenarioType,
    StarSettings,
    TrapKind,
)

PERIOD_TOLERANCE = 0.01
"""Spec 4.1: a period matches if it is within 1 % of the true period."""

BLS_DURATIONS_DAYS = (0.04, 0.08, 0.16, 0.24)
"""Box durations to try. astropy's default shortest period is twice the longest box, 0.48 d,
just below the shortest preset period (0.5 d). Longer boxes would push that limit above Easy's
shortest periods, and lowering the limit by hand lets very wide boxes fit noise at short
periods (a 0.32 d box with a 0.4 d floor found false peaks near 0.45 d in most Hard scenarios).
"""

MAX_Z = 4.0
"""Largest allowed difference between measured and true dip, in standard errors."""


def without_activity(settings: ScenarioSettings) -> ScenarioSettings:
    """The same scenario on a star with no starspots."""
    star = settings.star.model_copy(update={"activity_amplitude": 0.0})
    return settings.model_copy(update={"star": star})


def preset_planets(
    preset: Preset, count: int, *, trap_kinds: set[TrapKind] | None = None
) -> list[ScenarioSettings]:
    """The first ``count`` planet scenarios (settings) a preset produces, from seed 0 upwards."""
    found: list[ScenarioSettings] = []
    seed = 0
    while len(found) < count:
        settings = draw_settings(preset, seed)
        seed += 1
        if settings.type is not ScenarioType.PLANET:
            continue
        if trap_kinds is not None and settings.trap_kind not in trap_kinds:
            continue
        found.append(settings)
    return found


def custom_planet(
    radius_rearth: float, period_days: float, t0_days: float, impact_parameter: float
) -> ScenarioSettings:
    """A quiet star with a planted planet at low noise (100 ppm)."""
    return ScenarioSettings(
        seed=2026,
        preset=Preset.CUSTOM,
        type=ScenarioType.PLANET,
        star=StarSettings(radius_rsun=1.0, activity_amplitude=0.0, rotation_period_days=10.0),
        observation=ObservationSettings(noise_ppm=100.0, extra_gaps=False),
        planet=PlanetSettings(
            radius_rearth=radius_rearth,
            period_days=period_days,
            t0_days=t0_days,
            impact_parameter=impact_parameter,
        ),
    )


LOW_NOISE_CASES = [
    pytest.param(custom_planet(10.0, 3.0, 1.0, 0.0), id="jupiter-3d"),
    pytest.param(custom_planet(10.0, 0.55, 0.2, 0.2), id="jupiter-0.55d-shortest"),
    pytest.param(custom_planet(4.0, 0.7, 0.3, 0.5), id="neptune-0.7d"),
    pytest.param(custom_planet(2.0, 6.5, 2.0, 0.3), id="super-earth-6.5d"),
    pytest.param(custom_planet(3.0, 11.0, 4.0, 0.8), id="sub-neptune-11d-high-b"),
]


def transit_window(scenario: Scenario, duration_fraction: float = 1.0) -> np.ndarray:
    """Observed points within ``duration_fraction`` of the true transit window, folded."""
    planet = scenario.answer_key.planet
    assert planet is not None
    return in_transit_mask(
        scenario.time,
        period_days=planet.period_days,
        t0_days=planet.t0_days,
        duration_days=planet.duration_days * duration_fraction,
    )


def dip_z_score(scenario: Scenario) -> float:
    """(measured − true) mean dip inside the transit window, in standard errors."""
    inside = transit_window(scenario)
    outside = ~transit_window(scenario, duration_fraction=1.5)
    measured = scenario.flux[outside].mean() - scenario.flux[inside].mean()
    true = scenario.model_flux[outside].mean() - scenario.model_flux[inside].mean()
    sigma = scenario.flux_err[0] * np.sqrt(1 / inside.sum() + 1 / outside.sum())
    return float((measured - true) / sigma)


def bls_best_period(scenario: Scenario) -> float:
    """Period of the strongest BLS peak, using astropy's default period grid."""
    bls = BoxLeastSquares(scenario.time, scenario.flux, scenario.flux_err)
    periodogram = bls.autopower(BLS_DURATIONS_DAYS)
    return float(periodogram.period[np.argmax(periodogram.power)])


def period_recovered(scenario: Scenario) -> bool:
    planet = scenario.answer_key.planet
    assert planet is not None
    return abs(bls_best_period(scenario) / planet.period_days - 1) < PERIOD_TOLERANCE


# --- (a) direct check: fold at the true ephemeris ------------------------------------------


@pytest.mark.parametrize("settings", LOW_NOISE_CASES)
def test_low_noise_transit_has_the_true_depth(settings: ScenarioSettings) -> None:
    scenario = generate_scenario(settings)
    planet = scenario.answer_key.planet
    assert planet is not None
    # The central tenth of the transit is within a fraction of a percent of the full depth.
    core = transit_window(scenario, duration_fraction=0.1)
    baseline = scenario.flux[~transit_window(scenario, duration_fraction=1.5)].mean()
    measured = baseline - scenario.flux[core].mean()
    assert measured == pytest.approx(planet.depth, rel=0.05)
    assert abs(dip_z_score(scenario)) < MAX_Z


@pytest.mark.parametrize("preset", [Preset.EASY, Preset.MEDIUM, Preset.HARD, Preset.TRAP])
def test_preset_transits_match_the_true_model(preset: Preset) -> None:
    # Every planet the presets plant is in the data with the right depth and shape, to within
    # the noise, at the true period and t0.
    for settings in preset_planets(preset, 15):
        scenario = generate_scenario(without_activity(settings))
        assert abs(dip_z_score(scenario)) < MAX_Z, settings


@pytest.mark.parametrize("preset", [Preset.EASY, Preset.MEDIUM, Preset.HARD])
def test_folded_dip_snr_matches_expected_snr(preset: Preset) -> None:
    # The SNR of the folded dip should track the answer key's expected_snr. The expected SNR
    # uses the mid-transit depth, deeper than the window average, so the measured SNR is lower;
    # the ratio should stay between 0.4 and 1.2 (wide enough for the noise at SNR 6).
    for settings in preset_planets(preset, 15):
        scenario = generate_scenario(without_activity(settings))
        key = scenario.answer_key
        assert key.expected_snr is not None
        inside = transit_window(scenario)
        outside = ~transit_window(scenario, duration_fraction=1.5)
        dip = scenario.flux[outside].mean() - scenario.flux[inside].mean()
        measured_snr = dip / (scenario.flux_err[0] / np.sqrt(inside.sum()))
        assert 0.4 < measured_snr / key.expected_snr < 1.2, (settings.seed, measured_snr)


# --- (b) search check: astropy BoxLeastSquares ---------------------------------------------


@pytest.mark.slow
@pytest.mark.parametrize("settings", LOW_NOISE_CASES)
def test_bls_finds_low_noise_planet(settings: ScenarioSettings) -> None:
    assert period_recovered(generate_scenario(settings))


@pytest.mark.slow
def test_bls_finds_easy_planets_with_their_starspots() -> None:
    # Easy's starspots (at most 0.1 %) are weak enough to search without detrending.
    for settings in preset_planets(Preset.EASY, 6):
        assert period_recovered(generate_scenario(settings)), settings.seed


@pytest.mark.slow
def test_bls_finds_medium_planets() -> None:
    for settings in preset_planets(Preset.MEDIUM, 6):
        assert period_recovered(generate_scenario(without_activity(settings))), settings.seed


@pytest.mark.slow
def test_bls_finds_most_hard_planets() -> None:
    # Hard's SNR range (6-10) straddles the vetting threshold of 7, so some misses are expected
    # (spec 2.4). With these fixed seeds BLS finds 9 of 12; every miss has SNR 7.2 or less.
    scenarios = [
        generate_scenario(without_activity(settings))
        for settings in preset_planets(Preset.HARD, 12)
    ]
    found = [period_recovered(scenario) for scenario in scenarios]
    assert sum(found) >= 9
    for scenario, ok in zip(scenarios, found, strict=True):
        if not ok:
            assert scenario.answer_key.expected_snr is not None
            assert scenario.answer_key.expected_snr < 7.5


@pytest.mark.slow
def test_bls_finds_grazing_trap_planets() -> None:
    for settings in preset_planets(Preset.TRAP, 4, trap_kinds={TrapKind.GRAZING_PLANET}):
        assert period_recovered(generate_scenario(without_activity(settings))), settings.seed
