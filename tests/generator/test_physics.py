"""Tests for the generator's physical relations, checked against known Sun-Earth values."""

import math

import pytest

from exoplanet_lab.generator.physics import (
    EARTH_TO_SOLAR_RADIUS,
    inclination_deg,
    quadratic_limb_darkening,
    radius_ratio,
    scaled_semi_major_axis,
    stellar_mass_from_radius,
    transit_duration_days,
)

EARTH_YEAR_DAYS = 365.25
SUN_EARTH_A_OVER_RSTAR = 215.0  # 1 au / 1 R☉ ≈ 1.496e11 m / 6.957e8 m
EARTH_K = EARTH_TO_SOLAR_RADIUS


# --- star mass ---------------------------------------------------------------------------


def test_sun_has_one_solar_mass() -> None:
    assert stellar_mass_from_radius(1.0) == pytest.approx(1.0)


@pytest.mark.parametrize(("radius", "mass"), [(0.5, 0.420), (1.5, 1.660)])
def test_mass_at_range_edges(radius: float, mass: float) -> None:
    assert stellar_mass_from_radius(radius) == pytest.approx(mass, abs=0.001)


def test_mass_increases_with_radius() -> None:
    masses = [stellar_mass_from_radius(r) for r in (0.5, 0.8, 1.0, 1.2, 1.5)]
    assert masses == sorted(masses)


# --- radius ratio ------------------------------------------------------------------------


def test_earth_sun_radius_ratio() -> None:
    assert radius_ratio(1.0, 1.0) == pytest.approx(0.009168, rel=1e-3)


def test_jupiter_sun_radius_ratio() -> None:
    # Jupiter is about 11.2 Earth radii and about 0.103 solar radii.
    assert radius_ratio(11.2, 1.0) == pytest.approx(0.103, rel=0.01)


# --- Kepler's third law ------------------------------------------------------------------


def test_earth_orbit_is_215_solar_radii() -> None:
    a = scaled_semi_major_axis(EARTH_YEAR_DAYS, mass_msun=1.0, radius_rsun=1.0)
    assert a == pytest.approx(SUN_EARTH_A_OVER_RSTAR, rel=0.002)


def test_semi_major_axis_scales_as_period_to_two_thirds() -> None:
    a1 = scaled_semi_major_axis(1.0, 1.0, 1.0)
    a8 = scaled_semi_major_axis(8.0, 1.0, 1.0)
    assert a8 / a1 == pytest.approx(4.0)


def test_hot_jupiter_orbit() -> None:
    # A 3-day orbit around the Sun is about 0.04 au, i.e. about 8.6 solar radii.
    assert scaled_semi_major_axis(3.0, 1.0, 1.0) == pytest.approx(8.6, rel=0.02)


# --- inclination -------------------------------------------------------------------------


def test_central_transit_is_edge_on() -> None:
    assert inclination_deg(10.0, 0.0) == pytest.approx(90.0)


def test_inclination_from_impact_parameter() -> None:
    a = 10.0
    b = 0.5
    assert math.cos(math.radians(inclination_deg(a, b))) * a == pytest.approx(b)


def test_impact_parameter_larger_than_orbit_rejected() -> None:
    with pytest.raises(ValueError):
        inclination_deg(2.0, 3.0)


# --- transit duration --------------------------------------------------------------------


def test_earth_transit_lasts_about_13_hours() -> None:
    hours = 24 * transit_duration_days(EARTH_YEAR_DAYS, SUN_EARTH_A_OVER_RSTAR, EARTH_K, 0.0)
    assert hours == pytest.approx(13.1, abs=0.1)


def test_duration_shrinks_as_impact_parameter_grows() -> None:
    a = scaled_semi_major_axis(5.0, 1.0, 1.0)
    durations = [transit_duration_days(5.0, a, 0.1, b) for b in (0.0, 0.3, 0.6, 0.9, 1.05)]
    assert durations == sorted(durations, reverse=True)
    assert durations[-1] > 0  # b = 1.05 still grazes when k = 0.1


def test_no_transit_when_planet_misses_star() -> None:
    a = scaled_semi_major_axis(5.0, 1.0, 1.0)
    assert transit_duration_days(5.0, a, 0.1, 1.1) == 0.0
    assert transit_duration_days(5.0, a, 0.1, 1.2) == 0.0


def test_central_duration_matches_small_angle_formula() -> None:
    # For a wide orbit and b = 0, T14 ≈ P (1 + k) / (π a/R★).
    period, k = 10.0, 0.05
    a = scaled_semi_major_axis(period, 1.0, 1.0)
    expected = period * (1 + k) / (math.pi * a)
    assert transit_duration_days(period, a, k, 0.0) == pytest.approx(expected, rel=1e-3)


# --- limb darkening ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("radius", "teff", "u1", "u2"),
    [
        (0.5, 4000.0, 0.4090, 0.2526),
        (0.75, 4750.0, 0.4757, 0.1731),
        (1.0, 5750.0, 0.3075, 0.2743),
        (1.2, 6250.0, 0.2411, 0.3045),
        (1.5, 6750.0, 0.1982, 0.3168),
    ],
)
def test_limb_darkening_bins(radius: float, teff: float, u1: float, u2: float) -> None:
    ld = quadratic_limb_darkening(radius)
    assert (ld.teff_k, ld.u1, ld.u2) == (teff, u1, u2)


def test_limb_darkening_bin_edges() -> None:
    assert quadratic_limb_darkening(0.6499).teff_k == 4000.0
    assert quadratic_limb_darkening(0.65).teff_k == 4750.0


@pytest.mark.parametrize("radius", [0.5, 0.7, 1.0, 1.2, 1.5])
def test_limb_darkening_is_physical(radius: float) -> None:
    # Brightness must stay positive and fall towards the edge: u1 > 0, u1 + u2 < 1.
    ld = quadratic_limb_darkening(radius)
    assert ld.u1 > 0
    assert ld.u1 + ld.u2 < 1


# --- input checks ------------------------------------------------------------------------


@pytest.mark.parametrize(
    "call",
    [
        lambda: stellar_mass_from_radius(0.0),
        lambda: radius_ratio(-1.0, 1.0),
        lambda: scaled_semi_major_axis(0.0, 1.0, 1.0),
        lambda: transit_duration_days(5.0, 10.0, 0.1, -0.1),
        lambda: quadratic_limb_darkening(-1.0),
    ],
)
def test_invalid_inputs_rejected(call: object) -> None:
    with pytest.raises(ValueError):
        call()  # type: ignore[operator]
