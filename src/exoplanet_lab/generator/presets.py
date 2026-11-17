"""Difficulty presets: draw complete scenario settings from a preset and a seed (spec 2.4).

Difficulty is set by the expected signal-to-noise ratio (SNR), not by the noise level. For each
planet the preset draws a target SNR and then solves for the white noise that gives it:

    noise per point = depth × √N ÷ SNR

where depth is the noise-free model depth and N is the number of observed in-transit points. A
draw is rejected and repeated when the noise falls outside 100-3000 ppm or too few transits are
observed. ``no_planet`` scenarios in Medium and Hard solve for their noise with a "phantom"
planet that is then discarded, so the noise level never hints at the answer.

Every draw comes from the seed's PRESET stream. The time grid is built from the GAPS stream
exactly as :func:`generate_scenario` builds it, so the transit counts checked here are the ones
the final light curve has.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np

from exoplanet_lab.generator.rng import Stream, stream_rng
from exoplanet_lab.generator.scenario import (
    Scenario,
    count_observed_transits,
    generate_scenario,
    transit_stats,
)
from exoplanet_lab.generator.settings import (
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
from exoplanet_lab.generator.signals import binary_geometry, planet_geometry
from exoplanet_lab.generator.timeseries import (
    DOWNLINK_GAP_END,
    DOWNLINK_GAP_START,
    SECTOR_DAYS,
    TimeGrid,
    make_time_grid,
)

MAX_ATTEMPTS = 10_000
"""Draws to try before giving up. Real presets need a handful; this only guards against bugs."""

NOISE_PPM_RANGE = (100.0, 3000.0)
"""Allowed white noise per point, in ppm (spec 2.3)."""


@dataclass(frozen=True)
class Range:
    """A closed range to draw from, uniformly or log-uniformly."""

    low: float
    high: float
    log: bool = False

    def draw(self, rng: np.random.Generator) -> float:
        """One random value in the range."""
        if self.log:
            return math.exp(rng.uniform(math.log(self.low), math.log(self.high)))
        return float(rng.uniform(self.low, self.high))

    def __contains__(self, value: float) -> bool:
        return self.low <= value <= self.high


@dataclass(frozen=True)
class GradedPreset:
    """Ranges for Easy, Medium and Hard (spec 2.4 table)."""

    planet_fraction: float
    """Chance that a scenario has a planet; the rest are ``no_planet``."""
    snr: Range
    radius_rearth: Range
    period_days: Range
    impact_parameter: Range
    activity: Range
    rotation_days: Range
    extra_gap_chance: float
    min_transits: int


STAR_RADIUS = Range(0.5, 1.5)
"""Star radius in solar radii, the same in every preset."""

GRADED_PRESETS: dict[Preset, GradedPreset] = {
    Preset.EASY: GradedPreset(
        planet_fraction=1.0,
        snr=Range(30.0, 200.0, log=True),
        radius_rearth=Range(8.0, 15.0),
        period_days=Range(0.5, 6.0),
        impact_parameter=Range(0.0, 0.7),
        activity=Range(0.0, 0.001),
        rotation_days=Range(5.0, 15.0),
        extra_gap_chance=0.0,
        min_transits=4,
    ),
    Preset.MEDIUM: GradedPreset(
        planet_fraction=0.7,
        snr=Range(10.0, 30.0),
        radius_rearth=Range(2.5, 5.0),
        period_days=Range(1.0, 9.0),
        impact_parameter=Range(0.0, 0.8),
        activity=Range(0.001, 0.005),
        rotation_days=Range(2.0, 15.0),
        extra_gap_chance=0.5,
        min_transits=3,
    ),
    Preset.HARD: GradedPreset(
        planet_fraction=0.7,
        snr=Range(6.0, 10.0),
        radius_rearth=Range(0.8, 3.0),
        period_days=Range(1.0, 12.0),
        impact_parameter=Range(0.0, 0.9),
        activity=Range(0.005, 0.02),
        rotation_days=Range(1.0, 15.0),
        extra_gap_chance=0.5,
        min_transits=3,
    ),
}


@dataclass(frozen=True)
class TrapPlanet:
    """Ranges for the planet Trap kinds."""

    snr: Range
    radius_rearth: Range
    period_days: Range
    impact_parameter: Range


TRAP_EXTRA_GAP_CHANCE = 0.5
TRAP_ACTIVITY = Range(0.001, 0.005)
TRAP_ROTATION_DAYS = Range(2.0, 15.0)
TRAP_NOISE_PPM = Range(*NOISE_PPM_RANGE, log=True)
TRAP_MIN_TRANSITS = 2

TRAP_PLANETS: dict[TrapKind, TrapPlanet] = {
    TrapKind.GRAZING_PLANET: TrapPlanet(
        snr=Range(15.0, 50.0),
        radius_rearth=Range(8.0, 15.0),
        period_days=Range(1.0, 9.0),
        impact_parameter=Range(0.9, 1.05),
    ),
    TrapKind.TWO_TRANSIT: TrapPlanet(
        snr=Range(10.0, 30.0),
        radius_rearth=Range(2.0, 10.0),
        period_days=Range(9.0, 13.5),
        impact_parameter=Range(0.0, 0.9),
    ),
    TrapKind.ALIAS_GAP: TrapPlanet(
        snr=Range(10.0, 30.0),
        radius_rearth=Range(2.0, 10.0),
        period_days=Range(7.0, 13.4),
        impact_parameter=Range(0.0, 0.9),
    ),
}

BINARY_PERIOD_DAYS = Range(1.0, 9.0)
BINARY_IMPACT_PARAMETER = Range(0.0, 0.9)
TRAP_BINARIES: dict[TrapKind, tuple[Range, Range]] = {
    TrapKind.NEAR_EQUAL_EB: (Range(0.01, 0.05), Range(0.8, 1.0)),
    TrapKind.CLASSIC_EB: (Range(0.01, 0.30), Range(0.05, 0.60)),
}
"""(primary depth, secondary depth ÷ primary depth) for each binary Trap kind."""

SPOT_ONLY_ACTIVITY = Range(0.01, 0.02)
SPOT_ONLY_ROTATION_DAYS = Range(1.0, 5.0)
SPOT_ONLY_NOISE_PPM = Range(100.0, 1000.0, log=True)


# --- shared helpers ------------------------------------------------------------------------


def _time_grid(seed: int, extra_gaps: bool) -> TimeGrid:
    """The grid ``generate_scenario`` will build for this seed and gap setting."""
    return make_time_grid(stream_rng(seed, Stream.GAPS), extra_gaps=extra_gaps)


def _draw_star(rng: np.random.Generator, activity: Range, rotation_days: Range) -> StarSettings:
    return StarSettings(
        radius_rsun=STAR_RADIUS.draw(rng),
        activity_amplitude=activity.draw(rng),
        rotation_period_days=rotation_days.draw(rng),
    )


def solve_noise_ppm(
    planet: PlanetSettings,
    star: StarSettings,
    grid: TimeGrid,
    target_snr: float,
    transits_ok: Callable[[int], bool],
) -> float | None:
    """Noise per point (ppm) that gives ``target_snr``, or None if the draw must be repeated.

    The draw is rejected when the planet misses the star, when ``transits_ok`` rejects the
    number of observed transits, or when the noise falls outside 100-3000 ppm.
    """
    geometry = planet_geometry(planet, star)
    if geometry.duration_days <= 0:
        return None
    stats = transit_stats(geometry, grid)
    if not transits_ok(stats.n_transits_observed):
        return None
    noise_ppm = stats.depth * math.sqrt(stats.n_in_transit_points) / target_snr * 1e6
    low, high = NOISE_PPM_RANGE
    if not low <= noise_ppm <= high:
        return None
    return noise_ppm


def _exhausted(what: str) -> RuntimeError:
    return RuntimeError(f"no valid {what} found in {MAX_ATTEMPTS} draws")


# --- Easy, Medium, Hard --------------------------------------------------------------------


def _draw_graded(preset: Preset, seed: int, rng: np.random.Generator) -> ScenarioSettings:
    ranges = GRADED_PRESETS[preset]
    has_planet = rng.random() < ranges.planet_fraction
    extra_gaps = bool(rng.random() < ranges.extra_gap_chance)
    grid = _time_grid(seed, extra_gaps)

    for _ in range(MAX_ATTEMPTS):
        star = _draw_star(rng, ranges.activity, ranges.rotation_days)
        period = ranges.period_days.draw(rng)
        planet = PlanetSettings(
            radius_rearth=ranges.radius_rearth.draw(rng),
            period_days=period,
            t0_days=float(rng.uniform(0.0, period)),
            impact_parameter=ranges.impact_parameter.draw(rng),
        )
        target_snr = ranges.snr.draw(rng)
        noise_ppm = solve_noise_ppm(
            planet, star, grid, target_snr, lambda n: n >= ranges.min_transits
        )
        if noise_ppm is None:
            continue
        return ScenarioSettings(
            seed=seed,
            preset=preset,
            type=ScenarioType.PLANET if has_planet else ScenarioType.NO_PLANET,
            star=star,
            observation=ObservationSettings(noise_ppm=noise_ppm, extra_gaps=extra_gaps),
            # A no_planet scenario keeps the phantom planet's noise level but not the planet.
            planet=planet if has_planet else None,
        )
    raise _exhausted(f"{preset.value} scenario")


# --- Trap ----------------------------------------------------------------------------------


def _draw_trap_planet(
    kind: TrapKind, rng: np.random.Generator, grid: TimeGrid
) -> tuple[StarSettings, PlanetSettings, float]:
    """Star, planet and noise for a planet Trap kind."""
    ranges = TRAP_PLANETS[kind]
    for _ in range(MAX_ATTEMPTS):
        star = _draw_star(rng, TRAP_ACTIVITY, TRAP_ROTATION_DAYS)
        period = ranges.period_days.draw(rng)
        radius = ranges.radius_rearth.draw(rng)
        impact = ranges.impact_parameter.draw(rng)
        target_snr = ranges.snr.draw(rng)

        if kind is TrapKind.ALIAS_GAP:
            t0 = _alias_gap_t0(rng, star, radius, period, impact)
            if t0 is None:
                continue
        else:
            t0 = float(rng.uniform(0.0, period))
        planet = PlanetSettings(
            radius_rearth=radius, period_days=period, t0_days=t0, impact_parameter=impact
        )

        def transits_ok(n: int) -> bool:
            if kind is TrapKind.GRAZING_PLANET:
                return n >= TRAP_MIN_TRANSITS
            return n == 2  # two_transit, and alias_gap's two transits either side of the gap

        noise_ppm = solve_noise_ppm(planet, star, grid, target_snr, transits_ok)
        if noise_ppm is not None:
            return star, planet, noise_ppm
    raise _exhausted(f"{kind.value} scenario")


def _alias_gap_t0(
    rng: np.random.Generator, star: StarSettings, radius: float, period: float, impact: float
) -> float | None:
    """First transit time that puts the middle of exactly three transits inside the downlink gap.

    The middle transit's whole window lies in the gap, so only the outer two are seen. They are
    2P apart, so a period of 2P fits the data as well as the true period P. Returns None when
    this period and duration cannot be placed that way.
    """
    duration = planet_geometry(
        PlanetSettings(
            radius_rearth=radius, period_days=period, t0_days=0.0, impact_parameter=impact
        ),
        star,
    ).duration_days
    half = duration / 2
    if duration <= 0 or duration >= DOWNLINK_GAP_END - DOWNLINK_GAP_START:
        return None
    middle = float(rng.uniform(DOWNLINK_GAP_START + half, DOWNLINK_GAP_END - half))
    t0 = middle - period
    only_three = middle - 2 * period + half < 0 and middle + 2 * period - half > SECTOR_DAYS
    last_in_sector = middle + period + half <= SECTOR_DAYS
    if t0 < 0 or not only_three or not last_in_sector:
        return None
    return t0


def _draw_trap_binary(
    kind: TrapKind, rng: np.random.Generator, grid: TimeGrid
) -> tuple[StarSettings, BinarySettings]:
    """Star and binary for a binary Trap kind, with at least two observed primary eclipses."""
    primary_depth, secondary_ratio = TRAP_BINARIES[kind]
    for _ in range(MAX_ATTEMPTS):
        star = _draw_star(rng, TRAP_ACTIVITY, TRAP_ROTATION_DAYS)
        period = BINARY_PERIOD_DAYS.draw(rng)
        binary = BinarySettings(
            period_days=period,
            t0_days=float(rng.uniform(0.0, period)),
            primary_depth=primary_depth.draw(rng),
            secondary_ratio=secondary_ratio.draw(rng),
            impact_parameter=BINARY_IMPACT_PARAMETER.draw(rng),
        )
        try:
            primary = binary_geometry(binary, star).primary
        except ValueError:  # depth unreachable at this impact parameter, or stars overlap
            continue
        eclipses = count_observed_transits(
            grid.time,
            grid.observed,
            period_days=primary.period_days,
            t0_days=primary.t0_days,
            duration_days=primary.duration_days,
        )
        if eclipses >= TRAP_MIN_TRANSITS:
            return star, binary
    raise _exhausted(f"{kind.value} scenario")


def _draw_trap(seed: int, rng: np.random.Generator) -> ScenarioSettings:
    kinds = list(TrapKind)
    kind = kinds[int(rng.integers(len(kinds)))]
    extra_gaps = bool(rng.random() < TRAP_EXTRA_GAP_CHANCE)
    grid = _time_grid(seed, extra_gaps)
    common: dict[str, Any] = {
        "seed": seed,
        "preset": Preset.TRAP,
        "type": TRAP_KIND_TYPES[kind],
        "trap_kind": kind,
    }

    if kind is TrapKind.SPOT_ONLY:
        star = _draw_star(rng, SPOT_ONLY_ACTIVITY, SPOT_ONLY_ROTATION_DAYS)
        observation = ObservationSettings(
            noise_ppm=SPOT_ONLY_NOISE_PPM.draw(rng), extra_gaps=extra_gaps
        )
        return ScenarioSettings(**common, star=star, observation=observation)

    if kind in TRAP_BINARIES:
        star, binary = _draw_trap_binary(kind, rng, grid)
        observation = ObservationSettings(noise_ppm=TRAP_NOISE_PPM.draw(rng), extra_gaps=extra_gaps)
        return ScenarioSettings(**common, star=star, observation=observation, binary=binary)

    star, planet, noise_ppm = _draw_trap_planet(kind, rng, grid)
    observation = ObservationSettings(noise_ppm=noise_ppm, extra_gaps=extra_gaps)
    return ScenarioSettings(**common, star=star, observation=observation, planet=planet)


# --- public API ----------------------------------------------------------------------------


def draw_settings(preset: Preset, seed: int) -> ScenarioSettings:
    """Draw complete, valid scenario settings for a preset. Same preset and seed, same result.

    Raises:
        ValueError: for ``Preset.CUSTOM``, whose settings come from the user, not a draw.
    """
    if preset is Preset.CUSTOM:
        raise ValueError("the Custom preset has no draws; build ScenarioSettings directly")
    rng = stream_rng(seed, Stream.PRESET)
    if preset is Preset.TRAP:
        return _draw_trap(seed, rng)
    return _draw_graded(preset, seed, rng)


def generate_preset_scenario(preset: Preset, seed: int) -> Scenario:
    """Draw settings for a preset and generate the scenario they describe."""
    return generate_scenario(draw_settings(preset, seed))
