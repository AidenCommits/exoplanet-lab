"""Tests for the signal models: transits, eclipsing binaries, starspots and noise."""

import math

import numpy as np
import pytest

from exoplanet_lab.generator.physics import radius_ratio
from exoplanet_lab.generator.settings import BinarySettings, PlanetSettings, StarSettings
from exoplanet_lab.generator.signals import (
    TransitGeometry,
    binary_geometry,
    eclipsing_binary_model,
    planet_geometry,
    starspot_model,
    transit_depth,
    transit_model,
    white_noise,
)
from exoplanet_lab.generator.timeseries import CADENCE_DAYS, full_time_grid

TIME = full_time_grid()
SUN = StarSettings(radius_rsun=1.0, activity_amplitude=0.0, rotation_period_days=10.0)


def planet(**overrides: float) -> PlanetSettings:
    fields = {"radius_rearth": 10.0, "period_days": 3.0, "t0_days": 1.0, "impact_parameter": 0.0}
    fields.update(overrides)
    return PlanetSettings(**fields)


def binary(**overrides: float) -> BinarySettings:
    fields = {
        "period_days": 4.0,
        "t0_days": 1.0,
        "primary_depth": 0.10,
        "secondary_ratio": 0.4,
        "impact_parameter": 0.2,
    }
    fields.update(overrides)
    return BinarySettings(**fields)


# --- planet geometry and transit model ---------------------------------------------------


def test_planet_geometry_uses_star_and_planet() -> None:
    geometry = planet_geometry(planet(), SUN)
    assert geometry.radius_ratio == pytest.approx(radius_ratio(10.0, 1.0))
    assert geometry.inclination_deg == pytest.approx(90.0)
    assert geometry.limb_darkening.teff_k == 5750.0
    assert 0 < geometry.duration_days < geometry.period_days


def test_flux_is_one_out_of_transit() -> None:
    geometry = planet_geometry(planet(), SUN)
    flux = transit_model(TIME, geometry)
    phase = ((TIME - geometry.t0_days + geometry.period_days / 2) % geometry.period_days) - (
        geometry.period_days / 2
    )
    out_of_transit = np.abs(phase) > geometry.duration_days / 2 + CADENCE_DAYS
    assert np.all(flux[out_of_transit] == 1.0)
    assert np.all(flux <= 1.0)


def test_dips_occur_at_every_epoch() -> None:
    geometry = planet_geometry(planet(), SUN)
    flux = transit_model(TIME, geometry)
    epochs = geometry.t0_days + geometry.period_days * np.arange(9)
    epochs = epochs[epochs < TIME[-1]]
    for epoch in epochs:
        nearest = np.argmin(np.abs(TIME - epoch))
        assert flux[nearest] < 1.0 - 0.9 * transit_depth(geometry)


def test_points_in_transit_match_duration() -> None:
    geometry = planet_geometry(planet(), SUN)
    flux = transit_model(TIME, geometry)
    n_transits = 9  # t0 = 1, P = 3, sector 27.4 days: transits at 1, 4, ..., 25
    expected_points = n_transits * geometry.duration_days / CADENCE_DAYS
    assert np.sum(flux < 1.0) == pytest.approx(expected_points, abs=2 * n_transits)


def test_central_depth_matches_limb_darkening_formula() -> None:
    # For a small planet crossing the centre, depth = k² · I(centre) / I(average)
    # = k² / (1 − u1/3 − u2/6) for quadratic limb darkening.
    geometry = planet_geometry(planet(radius_rearth=2.0), SUN)
    u1, u2 = geometry.limb_darkening.u1, geometry.limb_darkening.u2
    expected = geometry.radius_ratio**2 / (1 - u1 / 3 - u2 / 6)
    assert transit_depth(geometry) == pytest.approx(expected, rel=0.01)


def test_grazing_transit_is_shallower_and_shorter() -> None:
    central = planet_geometry(planet(), SUN)
    grazing = planet_geometry(planet(impact_parameter=1.0), SUN)
    assert 0 < transit_depth(grazing) < transit_depth(central)
    assert 0 < grazing.duration_days < central.duration_days


def test_bigger_planet_gives_deeper_transit() -> None:
    depths = [transit_depth(planet_geometry(planet(radius_rearth=r), SUN)) for r in (1, 4, 10)]
    assert depths == sorted(depths)


# --- eclipsing binaries ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("star_radius", "depth", "impact_parameter"),
    [
        (1.0, 0.01, 0.0),
        (1.0, 0.10, 0.5),
        (0.5, 0.30, 0.9),  # deepest eclipse at the largest impact parameter
        (1.5, 0.30, 0.9),
        (1.5, 0.01, 0.9),
    ],
)
def test_primary_eclipse_has_requested_depth(
    star_radius: float, depth: float, impact_parameter: float
) -> None:
    star = StarSettings(radius_rsun=star_radius, activity_amplitude=0.0, rotation_period_days=5.0)
    geometry = binary_geometry(binary(primary_depth=depth, impact_parameter=impact_parameter), star)
    assert transit_depth(geometry.primary) == pytest.approx(depth, rel=1e-6)
    assert geometry.primary.radius_ratio <= 1.0


@pytest.mark.parametrize("secondary_ratio", [0.0, 0.4, 0.9, 1.0])
def test_eclipse_depths_and_phases(secondary_ratio: float) -> None:
    geometry = binary_geometry(binary(secondary_ratio=secondary_ratio), SUN)
    t0, period = geometry.primary.t0_days, geometry.primary.period_days
    times = np.array([t0, t0 + period / 2, t0 + period / 4, t0 + 3 * period / 4])
    flux = eclipsing_binary_model(times, geometry)
    assert 1 - flux[0] == pytest.approx(0.10, rel=1e-6)  # primary at phase 0
    assert 1 - flux[1] == pytest.approx(0.10 * secondary_ratio, rel=1e-6, abs=1e-12)  # phase 0.5
    assert flux[2] == flux[3] == 1.0  # quarter phases are outside both eclipses


def test_secondary_eclipse_has_no_other_dips() -> None:
    geometry = binary_geometry(binary(secondary_ratio=0.5), SUN)
    flux = eclipsing_binary_model(TIME, geometry)
    t0, period = geometry.primary.t0_days, geometry.primary.period_days
    phase = ((TIME - t0) / period) % 1.0
    half_width = geometry.primary.duration_days / period / 2 + CADENCE_DAYS / period
    away_from_eclipses = (np.abs(phase - 0.5) > half_width) & (
        np.minimum(phase, 1 - phase) > half_width
    )
    assert np.all(flux[away_from_eclipses] == 1.0)
    assert flux.min() == pytest.approx(0.90, abs=1e-3)


def test_unreachable_eclipse_depth_rejected() -> None:
    # A 90 % eclipse at b = 0.9 is impossible for a companion no bigger than the star. The
    # settings model would refuse this depth, so build it without validation.
    impossible = BinarySettings.model_construct(
        period_days=4.0, t0_days=1.0, primary_depth=0.9, secondary_ratio=0.5, impact_parameter=0.9
    )
    with pytest.raises(ValueError, match="no radius ratio"):
        binary_geometry(impossible, SUN)


# --- starspots ---------------------------------------------------------------------------


@pytest.mark.parametrize("amplitude", [0.001, 0.005, 0.02])
def test_starspot_peak_to_peak_equals_amplitude(amplitude: float) -> None:
    flux = starspot_model(
        TIME, np.random.default_rng(1), amplitude=amplitude, rotation_period_days=4
    )
    assert np.ptp(flux) == pytest.approx(amplitude)
    assert flux.mean() == pytest.approx(1.0)


@pytest.mark.parametrize("rotation_period", [2.0, 5.0, 9.0])
@pytest.mark.parametrize("seed", range(5))
def test_starspot_signal_repeats_at_rotation_period(rotation_period: float, seed: int) -> None:
    flux = starspot_model(
        TIME, np.random.default_rng(seed), amplitude=0.01, rotation_period_days=rotation_period
    )
    power = np.abs(np.fft.rfft(flux - flux.mean())) ** 2
    frequencies = np.fft.rfftfreq(TIME.size, d=CADENCE_DAYS)
    peak_frequency = frequencies[np.argmax(power)]
    resolution = 1 / (TIME[-1] - TIME[0])
    assert peak_frequency == pytest.approx(1 / rotation_period, abs=1.5 * resolution)


def test_zero_activity_is_flat_and_uses_same_draws() -> None:
    quiet_rng = np.random.default_rng(3)
    active_rng = np.random.default_rng(3)
    flat = starspot_model(TIME, quiet_rng, amplitude=0.0, rotation_period_days=5)
    starspot_model(TIME, active_rng, amplitude=0.01, rotation_period_days=5)
    assert np.all(flat == 1.0)
    assert quiet_rng.bit_generator.state == active_rng.bit_generator.state


def test_starspots_are_reproducible() -> None:
    first = starspot_model(TIME, np.random.default_rng(8), amplitude=0.01, rotation_period_days=3)
    second = starspot_model(TIME, np.random.default_rng(8), amplitude=0.01, rotation_period_days=3)
    other = starspot_model(TIME, np.random.default_rng(9), amplitude=0.01, rotation_period_days=3)
    assert np.array_equal(first, second)
    assert not np.array_equal(first, other)


def test_starspot_amplitude_drifts() -> None:
    # The envelope should make the swing in one rotation differ from the swing in another.
    rotation = 3.0
    flux = starspot_model(
        TIME, np.random.default_rng(4), amplitude=0.01, rotation_period_days=rotation
    )
    per_rotation = [
        np.ptp(flux[(TIME >= start) & (TIME < start + rotation)])
        for start in np.arange(0, TIME[-1] - rotation, rotation)
    ]
    assert max(per_rotation) / min(per_rotation) > 1.2


# --- white noise -------------------------------------------------------------------------


@pytest.mark.parametrize("noise_ppm", [100.0, 1000.0, 3000.0])
def test_noise_has_requested_scatter(noise_ppm: float) -> None:
    noise = white_noise(TIME.size, np.random.default_rng(0), noise_ppm=noise_ppm)
    assert noise.std() == pytest.approx(noise_ppm * 1e-6, rel=0.03)
    assert abs(noise.mean()) < 5 * noise_ppm * 1e-6 / math.sqrt(TIME.size)


def test_noise_is_reproducible() -> None:
    first = white_noise(100, np.random.default_rng(5), noise_ppm=500)
    second = white_noise(100, np.random.default_rng(5), noise_ppm=500)
    assert np.array_equal(first, second)


# --- shared helpers ----------------------------------------------------------------------


def test_transit_geometry_is_frozen() -> None:
    geometry = planet_geometry(planet(), SUN)
    assert isinstance(geometry, TransitGeometry)
    with pytest.raises(AttributeError):
        geometry.period_days = 5.0  # type: ignore[misc]
