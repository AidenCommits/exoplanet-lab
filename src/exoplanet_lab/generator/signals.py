"""Signal models: planet transits, eclipsing binaries, starspot activity and white noise.

Every function works on any time array; the generator calls them on the full time grid and
applies the gap mask last (see ``timeseries``). Transit and eclipse models are noise-free and
equal 1 out of transit; the starspot model is a multiplicative factor around 1; white noise is
additive.
"""

import math
from dataclasses import dataclass

import batman
import numpy as np
from numpy.typing import NDArray
from scipy.optimize import brentq

from exoplanet_lab.generator.physics import (
    LimbDarkening,
    inclination_deg,
    quadratic_limb_darkening,
    radius_ratio,
    scaled_semi_major_axis,
    stellar_mass_from_radius,
    transit_duration_days,
)
from exoplanet_lab.generator.settings import BinarySettings, PlanetSettings, StarSettings

FloatArray = NDArray[np.float64]

# --- planet transits ---------------------------------------------------------------------


@dataclass(frozen=True)
class TransitGeometry:
    """Everything batman needs to draw one transit, plus the derived duration."""

    period_days: float
    t0_days: float
    radius_ratio: float
    """Radius of the transiting body over the star's radius, k."""
    a_over_rstar: float
    inclination_deg: float
    impact_parameter: float
    duration_days: float
    """Total duration T14, first to last contact."""
    limb_darkening: LimbDarkening


def planet_geometry(planet: PlanetSettings, star: StarSettings) -> TransitGeometry:
    """Derive the transit geometry of a planet from its settings and its star."""
    mass = stellar_mass_from_radius(star.radius_rsun)
    k = radius_ratio(planet.radius_rearth, star.radius_rsun)
    a = scaled_semi_major_axis(planet.period_days, mass, star.radius_rsun)
    return TransitGeometry(
        period_days=planet.period_days,
        t0_days=planet.t0_days,
        radius_ratio=k,
        a_over_rstar=a,
        inclination_deg=inclination_deg(a, planet.impact_parameter),
        impact_parameter=planet.impact_parameter,
        duration_days=transit_duration_days(planet.period_days, a, k, planet.impact_parameter),
        limb_darkening=quadratic_limb_darkening(star.radius_rsun),
    )


def _batman_params(geometry: TransitGeometry) -> batman.TransitParams:
    """batman parameters for a circular orbit with quadratic limb darkening."""
    params = batman.TransitParams()
    params.t0 = geometry.t0_days
    params.per = geometry.period_days
    params.rp = geometry.radius_ratio
    params.a = geometry.a_over_rstar
    params.inc = geometry.inclination_deg
    params.ecc = 0.0
    params.w = 90.0
    params.u = [geometry.limb_darkening.u1, geometry.limb_darkening.u2]
    params.limb_dark = "quadratic"
    return params


def transit_model(time: FloatArray, geometry: TransitGeometry) -> FloatArray:
    """Noise-free relative flux of a star with this transit: 1 out of transit, < 1 in it."""
    params = _batman_params(geometry)
    time = np.ascontiguousarray(time, dtype=np.float64)
    return np.asarray(batman.TransitModel(params, time).light_curve(params), dtype=np.float64)


def transit_depth(geometry: TransitGeometry) -> float:
    """True depth: the noise-free model's dip at mid-transit.

    Because of limb darkening this is not exactly k²: a central transit blocks the bright centre
    of the star and is deeper than k², a grazing one blocks the dim edge and is shallower.
    """
    return float(1.0 - transit_model(np.array([geometry.t0_days]), geometry)[0])


# --- eclipsing binaries ------------------------------------------------------------------


@dataclass(frozen=True)
class BinaryGeometry:
    """Geometry of an eclipsing binary and the depths of its two eclipses."""

    primary: TransitGeometry
    """The primary eclipse: the second star passing in front of the first."""
    primary_depth: float
    secondary_depth: float
    secondary_mass_msun: float


_MIN_BINARY_RADIUS_RATIO = 0.01
_MAX_BINARY_RADIUS_RATIO = 1.0


def binary_geometry(binary: BinarySettings, star: StarSettings) -> BinaryGeometry:
    """Derive an eclipsing binary's geometry so the primary eclipse has the requested depth.

    The second star's radius ratio is solved with a root finder. Its mass follows from its
    radius with the same main-sequence relation, and the orbit uses the combined mass.

    Raises:
        ValueError: if no radius ratio gives the requested depth, or the stars would overlap.
    """
    mass_1 = stellar_mass_from_radius(star.radius_rsun)
    limb_darkening = quadratic_limb_darkening(star.radius_rsun)

    def geometry_for(k: float) -> tuple[TransitGeometry, float]:
        mass_2 = stellar_mass_from_radius(k * star.radius_rsun)
        a = scaled_semi_major_axis(binary.period_days, mass_1 + mass_2, star.radius_rsun)
        geometry = TransitGeometry(
            period_days=binary.period_days,
            t0_days=binary.t0_days,
            radius_ratio=k,
            a_over_rstar=a,
            inclination_deg=inclination_deg(a, binary.impact_parameter),
            impact_parameter=binary.impact_parameter,
            duration_days=transit_duration_days(binary.period_days, a, k, binary.impact_parameter),
            limb_darkening=limb_darkening,
        )
        return geometry, mass_2

    def depth_error(k: float) -> float:
        return transit_depth(geometry_for(k)[0]) - binary.primary_depth

    low, high = _MIN_BINARY_RADIUS_RATIO, _MAX_BINARY_RADIUS_RATIO
    if depth_error(low) > 0 or depth_error(high) < 0:
        raise ValueError(
            f"no radius ratio in [{low}, {high}] gives a primary depth of {binary.primary_depth} "
            f"at impact parameter {binary.impact_parameter}"
        )
    k = float(brentq(depth_error, low, high, xtol=1e-10))
    geometry, mass_2 = geometry_for(k)
    if geometry.a_over_rstar <= 1 + k:
        raise ValueError("the orbit is too tight: the two stars would overlap")
    return BinaryGeometry(
        primary=geometry,
        primary_depth=binary.primary_depth,
        secondary_depth=binary.secondary_ratio * binary.primary_depth,
        secondary_mass_msun=mass_2,
    )


def _secondary_eclipse_shape(time: FloatArray, geometry: TransitGeometry) -> FloatArray:
    """Fraction of the second star hidden behind the first: 0 outside the eclipse, 1 at full.

    Uses batman's secondary-eclipse model (a uniform disk going behind the star) at phase 0.5.
    """
    params = _batman_params(geometry)
    params.fp = 1.0
    params.t_secondary = geometry.t0_days + geometry.period_days / 2
    time = np.ascontiguousarray(time, dtype=np.float64)
    model = batman.TransitModel(params, time, transittype="secondary")
    flux = np.asarray(model.light_curve(params), dtype=np.float64)
    fp = float(params.fp)
    return np.asarray((1.0 + fp - flux) / fp, dtype=np.float64)


def eclipsing_binary_model(time: FloatArray, geometry: BinaryGeometry) -> FloatArray:
    """Noise-free relative flux of an eclipsing binary: 1 outside eclipses.

    The secondary eclipse sits at phase 0.5 and is scaled so its deepest point equals
    ``secondary_depth`` exactly; its depth is set directly, not derived from temperatures.
    """
    flux = transit_model(time, geometry.primary)
    if geometry.secondary_depth == 0:
        return flux
    shape = _secondary_eclipse_shape(time, geometry.primary)
    mid_secondary = np.array([geometry.primary.t0_days + geometry.primary.period_days / 2])
    peak = float(_secondary_eclipse_shape(mid_secondary, geometry.primary)[0])
    return np.asarray(flux - geometry.secondary_depth * shape / peak, dtype=np.float64)


# --- starspots and noise -----------------------------------------------------------------

HARMONIC_RATIO_RANGE = (0.0, 0.5)
"""Range for the strength of the half-period wave relative to the main wave."""

ENVELOPE_PERIOD_RANGE = (2.0, 3.0)
"""Range for how slowly spots grow and fade, in rotation periods."""

ENVELOPE_DEPTH_RANGE = (0.2, 0.4)
"""Range for how much the spot amplitude rises and falls (0.3 = ±30 %)."""


def starspot_model(
    time: FloatArray,
    rng: np.random.Generator,
    *,
    amplitude: float,
    rotation_period_days: float,
) -> FloatArray:
    """Multiplicative brightness change from rotating, slowly evolving starspots.

    A sine wave at the rotation period plus a weaker one at half the period (two spot groups),
    with random phases, multiplied by a slow envelope so the pattern never repeats exactly.
    The result is scaled so its peak-to-peak range over ``time`` equals ``amplitude``.

    ``rng`` should be the generator's dedicated activity stream. It always makes the same
    draws, whatever the amplitude, so changing the amplitude never shifts other random values.
    """
    if amplitude < 0 or rotation_period_days <= 0:
        raise ValueError("amplitude must be non-negative and rotation_period_days positive")
    phase_1, phase_2, envelope_phase = rng.uniform(0.0, 2 * math.pi, size=3)
    harmonic_ratio = rng.uniform(*HARMONIC_RATIO_RANGE)
    envelope_period = rng.uniform(*ENVELOPE_PERIOD_RANGE) * rotation_period_days
    envelope_depth = rng.uniform(*ENVELOPE_DEPTH_RANGE)

    if amplitude == 0:
        return np.ones_like(time, dtype=np.float64)
    omega = 2 * math.pi / rotation_period_days
    wave = np.sin(omega * time + phase_1) + harmonic_ratio * np.sin(2 * omega * time + phase_2)
    envelope = 1 + envelope_depth * np.sin(2 * math.pi * time / envelope_period + envelope_phase)
    signal = wave * envelope
    signal = (signal - signal.mean()) / np.ptp(signal) * amplitude
    return np.asarray(1.0 + signal, dtype=np.float64)


def white_noise(n_points: int, rng: np.random.Generator, *, noise_ppm: float) -> FloatArray:
    """Independent Gaussian noise with standard deviation ``noise_ppm`` parts per million."""
    if n_points < 0 or noise_ppm < 0:
        raise ValueError("n_points and noise_ppm must be non-negative")
    return rng.normal(0.0, noise_ppm * 1e-6, size=n_points)
