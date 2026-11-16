"""Physical relations: star mass, orbit geometry, transit duration and limb darkening.

All orbits are circular (spec 2.3). Units are noted on every function: radii in solar or Earth
radii, periods and durations in days, angles in degrees.
"""

import math
from dataclasses import dataclass

# IAU 2015 nominal values (Resolution B3), in SI units.
SOLAR_RADIUS_M = 6.957e8
EARTH_RADIUS_M = 6.3781e6
SOLAR_GM_M3_PER_S2 = 1.3271244e20
SECONDS_PER_DAY = 86_400.0

EARTH_TO_SOLAR_RADIUS = EARTH_RADIUS_M / SOLAR_RADIUS_M
"""One Earth radius in solar radii (about 0.00917)."""

MASS_RADIUS_EXPONENT = 1.25
"""Main-sequence approximation R ∝ M^0.8, inverted: M = R^1.25 (solar units)."""


def stellar_mass_from_radius(radius_rsun: float) -> float:
    """Main-sequence star mass in solar masses from its radius in solar radii.

    Uses R ∝ M^0.8, a standard rough relation for main-sequence stars of about 0.5-1.5 R☉.
    """
    if radius_rsun <= 0:
        raise ValueError("radius_rsun must be positive")
    return float(radius_rsun**MASS_RADIUS_EXPONENT)


def radius_ratio(planet_radius_rearth: float, star_radius_rsun: float) -> float:
    """Planet-to-star radius ratio k = Rₚ/R★ (dimensionless)."""
    if planet_radius_rearth <= 0 or star_radius_rsun <= 0:
        raise ValueError("radii must be positive")
    return planet_radius_rearth * EARTH_TO_SOLAR_RADIUS / star_radius_rsun


def scaled_semi_major_axis(period_days: float, mass_msun: float, radius_rsun: float) -> float:
    """Orbit radius divided by the star's radius, a/R★, from Kepler's third law.

    a³ = G·M·P² / 4π². The planet's own mass is neglected.
    """
    if period_days <= 0 or mass_msun <= 0 or radius_rsun <= 0:
        raise ValueError("period, mass and radius must be positive")
    period_s = period_days * SECONDS_PER_DAY
    a_m = math.cbrt(SOLAR_GM_M3_PER_S2 * mass_msun * period_s**2 / (4 * math.pi**2))
    return a_m / (radius_rsun * SOLAR_RADIUS_M)


def inclination_deg(a_over_rstar: float, impact_parameter: float) -> float:
    """Orbital inclination in degrees from a/R★ and the impact parameter (circular orbit).

    cos i = b / (a/R★). An impact parameter of 0 gives i = 90° (edge-on).
    """
    if a_over_rstar <= 0 or impact_parameter < 0:
        raise ValueError("a_over_rstar must be positive and impact_parameter non-negative")
    if impact_parameter > a_over_rstar:
        raise ValueError("impact_parameter cannot exceed a_over_rstar")
    return math.degrees(math.acos(impact_parameter / a_over_rstar))


def transit_duration_days(
    period_days: float, a_over_rstar: float, radius_ratio: float, impact_parameter: float
) -> float:
    """Total transit duration T14 (first to last contact) in days, for a circular orbit.

    T14 = (P/π) · arcsin( √((1 + k)² − b²) / ((a/R★) · sin i) ), from Winn (2010), eq. 14.
    Returns 0 when the planet misses the star (b ≥ 1 + k).
    """
    if period_days <= 0 or a_over_rstar <= 0 or radius_ratio <= 0 or impact_parameter < 0:
        raise ValueError("period, a/R★ and k must be positive; b must be non-negative")
    chord_sq = (1 + radius_ratio) ** 2 - impact_parameter**2
    if chord_sq <= 0:
        return 0.0
    sin_i = math.sin(math.radians(inclination_deg(a_over_rstar, impact_parameter)))
    argument = min(1.0, math.sqrt(chord_sq) / (a_over_rstar * sin_i))
    return period_days / math.pi * math.asin(argument)


@dataclass(frozen=True)
class LimbDarkening:
    """Quadratic limb-darkening coefficients for one star, and the temperature they belong to."""

    teff_k: float
    u1: float
    u2: float


# Claret (2017), A&A 600, A30: TESS-band quadratic coefficients from ATLAS models, VizieR table
# J/A+A/600/A30/table25, least-squares method (columns aLSM, bLSM), log g = 4.5, [M/H] = 0,
# microturbulence 2 km/s. Values copied from the table.
#
# Each row: (largest star radius in R☉ for this bin, Teff in K, u1, u2). The radius bins map
# main-sequence stars to a representative temperature: late K / early M, mid K, Sun-like G,
# late F, mid F. This mapping is approximate; it only has to pick a sensible coefficient pair.
_LIMB_DARKENING_TABLE: tuple[tuple[float, float, float, float], ...] = (
    (0.65, 4000.0, 0.4090, 0.2526),
    (0.85, 4750.0, 0.4757, 0.1731),
    (1.10, 5750.0, 0.3075, 0.2743),
    (1.30, 6250.0, 0.2411, 0.3045),
    (math.inf, 6750.0, 0.1982, 0.3168),
)


def quadratic_limb_darkening(radius_rsun: float) -> LimbDarkening:
    """TESS-band quadratic limb-darkening coefficients for a main-sequence star of this radius.

    Limb darkening makes a star's disk dimmer at its edge than at its centre, which rounds the
    bottom of a transit. Coefficients are from Claret (2017); see ``_LIMB_DARKENING_TABLE``.
    """
    if radius_rsun <= 0:
        raise ValueError("radius_rsun must be positive")
    for max_radius, teff, u1, u2 in _LIMB_DARKENING_TABLE:
        if radius_rsun < max_radius:
            return LimbDarkening(teff_k=teff, u1=u1, u2=u2)
    raise AssertionError("unreachable: the last bin has no upper limit")
