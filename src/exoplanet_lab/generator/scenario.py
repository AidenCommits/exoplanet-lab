"""Scenario assembly: turn fully specified settings into a light curve and its answer key.

The flux is built on the full time grid as

    raw = signal × starspots + white noise

where ``signal`` is the noise-free transit or eclipse model (1 for ``no_planet``). Gap points are
dropped last, then flux and flux errors are divided by the median of the observed flux so the
light curve has a median of 1 (spec 2.2). Every random draw comes from its own stream (see
``rng``), so turning extra gaps on or off changes which points remain, but not the raw values of
the points that remain. The median normalization can rescale them by a common factor.

Presets (which draw the settings) are built on top of this module; here the settings are taken
as given, which is exactly the Custom preset.
"""

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from exoplanet_lab.generator.answer_key import (
    AnswerKey,
    BinaryTruth,
    PlanetTruth,
    StarTruth,
    scenario_id,
)
from exoplanet_lab.generator.physics import quadratic_limb_darkening, stellar_mass_from_radius
from exoplanet_lab.generator.rng import Stream, stream_rng
from exoplanet_lab.generator.settings import ScenarioSettings
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
from exoplanet_lab.generator.timeseries import CADENCE_DAYS, TimeGrid, make_time_grid

FloatArray = NDArray[np.float64]
BoolArray = NDArray[np.bool_]

MIN_OBSERVED_TRANSITS = 2
"""Fewest observed transits any planet scenario may have (spec 2.3). Presets ask for more."""

MIN_OBSERVED_FRACTION = 0.5
"""A transit counts as observed when at least this fraction of its points lies outside gaps."""


@dataclass(frozen=True)
class TransitStats:
    """How much of a planet's transit signal the observed data contains."""

    depth: float
    """Noise-free depth at mid-transit."""
    n_transits_observed: int
    n_in_transit_points: int
    """Observed points inside any transit window."""


@dataclass(frozen=True)
class Scenario:
    """One generated scenario: the observed light curve, the noise-free truth, and the key.

    All arrays cover the observed points only and have the same length.
    """

    time: FloatArray
    """Time stamps in days from the start of the sector."""
    flux: FloatArray
    """Relative flux, normalized to a median of 1."""
    flux_err: FloatArray
    """1σ uncertainty of each flux point (the white-noise level after normalization)."""
    model_flux: FloatArray
    """Noise-free transit or eclipse model, without starspots: 1 outside transits/eclipses."""
    answer_key: AnswerKey


# --- transit bookkeeping -------------------------------------------------------------------


def in_transit_mask(
    time: FloatArray, *, period_days: float, t0_days: float, duration_days: float
) -> BoolArray:
    """True for each time stamp within half a transit duration of some mid-transit time."""
    phase = (time - t0_days + period_days / 2) % period_days - period_days / 2
    return np.asarray(np.abs(phase) < duration_days / 2, dtype=np.bool_)


def count_observed_transits(
    time: FloatArray,
    observed: BoolArray,
    *,
    period_days: float,
    t0_days: float,
    duration_days: float,
) -> int:
    """Number of transits with at least half of their points observed.

    A transit's full point count is its duration divided by the cadence. Comparing against that,
    rather than against the points that happen to be on the grid, means a transit cut off by the
    start or end of the sector is judged the same way as one cut off by a gap.
    """
    if duration_days <= 0:
        return 0
    expected_points = duration_days / CADENCE_DAYS
    observed_time = time[observed]
    first_epoch = math.floor((time[0] - t0_days) / period_days)
    last_epoch = math.ceil((time[-1] - t0_days) / period_days)
    count = 0
    for epoch in range(first_epoch, last_epoch + 1):
        mid = t0_days + epoch * period_days
        n_seen = int(np.count_nonzero(np.abs(observed_time - mid) < duration_days / 2))
        if n_seen >= MIN_OBSERVED_FRACTION * expected_points:
            count += 1
    return count


def transit_stats(geometry: TransitGeometry, grid: TimeGrid) -> TransitStats:
    """Depth, observed transit count and observed in-transit point count for a planet."""
    window = {
        "period_days": geometry.period_days,
        "t0_days": geometry.t0_days,
        "duration_days": geometry.duration_days,
    }
    in_transit = in_transit_mask(grid.time, **window)
    return TransitStats(
        depth=transit_depth(geometry),
        n_transits_observed=count_observed_transits(grid.time, grid.observed, **window),
        n_in_transit_points=int(np.count_nonzero(in_transit & grid.observed)),
    )


def expected_snr(depth: float, noise_ppm: float, n_in_transit_points: int) -> float:
    """White-noise transit SNR: depth ÷ noise per point × √(observed in-transit points)."""
    if noise_ppm <= 0:
        raise ValueError("noise_ppm must be positive")
    return depth / (noise_ppm * 1e-6) * math.sqrt(n_in_transit_points)


# --- assembly ------------------------------------------------------------------------------


def _star_truth(settings: ScenarioSettings) -> StarTruth:
    star = settings.star
    limb_darkening = quadratic_limb_darkening(star.radius_rsun)
    return StarTruth(
        radius_rsun=star.radius_rsun,
        mass_msun=stellar_mass_from_radius(star.radius_rsun),
        teff_k=limb_darkening.teff_k,
        limb_darkening_u1=limb_darkening.u1,
        limb_darkening_u2=limb_darkening.u2,
        noise_ppm=settings.observation.noise_ppm,
        activity_amplitude=star.activity_amplitude,
        rotation_period_days=star.rotation_period_days,
    )


def generate_scenario(settings: ScenarioSettings) -> Scenario:
    """Generate the light curve and answer key described by ``settings``.

    The same settings always give exactly the same scenario.

    Raises:
        ValueError: if a planet misses its star, or fewer than ``MIN_OBSERVED_TRANSITS`` of its
            transits are observed; or if the binary settings are not physically possible.
    """
    grid = make_time_grid(
        stream_rng(settings.seed, Stream.GAPS), extra_gaps=settings.observation.extra_gaps
    )

    planet_truth: PlanetTruth | None = None
    binary_truth: BinaryTruth | None = None
    snr: float | None = None
    signal = np.ones_like(grid.time)

    if settings.planet is not None:
        geometry = planet_geometry(settings.planet, settings.star)
        if geometry.duration_days <= 0:
            raise ValueError("the planet misses the star: impact parameter is too large")
        stats = transit_stats(geometry, grid)
        if stats.n_transits_observed < MIN_OBSERVED_TRANSITS:
            raise ValueError(
                f"only {stats.n_transits_observed} transit(s) observed; "
                f"at least {MIN_OBSERVED_TRANSITS} are needed"
            )
        signal = transit_model(grid.time, geometry)
        snr = expected_snr(stats.depth, settings.observation.noise_ppm, stats.n_in_transit_points)
        planet_truth = PlanetTruth(
            period_days=geometry.period_days,
            t0_days=geometry.t0_days,
            duration_days=geometry.duration_days,
            depth=stats.depth,
            radius_ratio=geometry.radius_ratio,
            radius_rearth=settings.planet.radius_rearth,
            a_over_rstar=geometry.a_over_rstar,
            impact_parameter=geometry.impact_parameter,
            inclination_deg=geometry.inclination_deg,
            n_transits_observed=stats.n_transits_observed,
            n_in_transit_points=stats.n_in_transit_points,
        )
    elif settings.binary is not None:
        eb = binary_geometry(settings.binary, settings.star)
        signal = eclipsing_binary_model(grid.time, eb)
        binary_truth = BinaryTruth(
            period_days=eb.primary.period_days,
            t0_days=eb.primary.t0_days,
            primary_depth=eb.primary_depth,
            secondary_depth=eb.secondary_depth,
            radius_ratio=eb.primary.radius_ratio,
            a_over_rstar=eb.primary.a_over_rstar,
            impact_parameter=eb.primary.impact_parameter,
            companion_mass_msun=eb.secondary_mass_msun,
        )

    spots = starspot_model(
        grid.time,
        stream_rng(settings.seed, Stream.ACTIVITY),
        amplitude=settings.star.activity_amplitude,
        rotation_period_days=settings.star.rotation_period_days,
    )
    noise = white_noise(
        grid.time.size,
        stream_rng(settings.seed, Stream.NOISE),
        noise_ppm=settings.observation.noise_ppm,
    )
    raw = signal * spots + noise

    observed = grid.observed
    median = float(np.median(raw[observed]))
    flux = raw[observed] / median
    flux_err = np.full(flux.shape, settings.observation.noise_ppm * 1e-6 / median)

    answer_key = AnswerKey(
        scenario_id=scenario_id(settings),
        seed=settings.seed,
        preset=settings.preset,
        type=settings.type,
        has_planet=planet_truth is not None,
        trap_kind=settings.trap_kind,
        expected_snr=snr,
        star=_star_truth(settings),
        planet=planet_truth,
        binary=binary_truth,
        gaps=grid.gaps,
        settings=settings,
    )
    return Scenario(
        time=grid.observed_time,
        flux=np.asarray(flux, dtype=np.float64),
        flux_err=flux_err,
        model_flux=np.asarray(signal[observed], dtype=np.float64),
        answer_key=answer_key,
    )
