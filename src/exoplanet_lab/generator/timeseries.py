"""TESS-like time sampling: one sector at 2-minute cadence with data gaps (spec 2.2).

The grid always covers the whole sector. Gaps are returned as a mask of observed points rather
than removed, so the rest of the generator can compute signals and noise on the full grid and
drop gap points last. That way, switching extra gaps on or off never changes the flux at the
points that remain.
"""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

CADENCE_DAYS = 2.0 / (24 * 60)
"""TESS 2-minute cadence, in days (720 points per day)."""

SECTOR_DAYS = 27.4
"""Length of one TESS sector, in days."""

N_POINTS = round(SECTOR_DAYS / CADENCE_DAYS)
"""Number of points in the full grid (19 728)."""

DOWNLINK_GAP_DAYS = 1.0
DOWNLINK_GAP_START = (SECTOR_DAYS - DOWNLINK_GAP_DAYS) / 2
DOWNLINK_GAP_END = DOWNLINK_GAP_START + DOWNLINK_GAP_DAYS
"""The mid-sector gap while TESS sends its data to Earth: days 13.2 to 14.2."""

EXTRA_GAP_COUNT_RANGE = (1, 3)
"""Inclusive range for the number of extra random gaps."""

EXTRA_GAP_LENGTH_RANGE_DAYS = (0.2, 1.0)
"""Range for the length of each extra random gap, in days."""

Gap = tuple[float, float]
"""A gap as (start, end) in days; points with start <= t < end are not observed."""


@dataclass(frozen=True)
class TimeGrid:
    """The full time grid of one sector and which of its points were observed."""

    time: NDArray[np.float64]
    """Every 2-minute time stamp in the sector, in days from the start."""
    observed: NDArray[np.bool_]
    """True where the point lies outside every gap."""
    gaps: tuple[Gap, ...]
    """All gaps, the downlink gap first."""

    @property
    def observed_time(self) -> NDArray[np.float64]:
        """Time stamps of the observed points only."""
        return self.time[self.observed]


def full_time_grid() -> NDArray[np.float64]:
    """Every 2-minute time stamp in one sector, starting at 0 days."""
    return np.arange(N_POINTS, dtype=np.float64) * CADENCE_DAYS


def draw_extra_gaps(rng: np.random.Generator) -> tuple[Gap, ...]:
    """Draw 1-3 random gaps, each 0.2-1.0 days long, placed uniformly within the sector.

    Gaps may overlap each other or the downlink gap.
    """
    low, high = EXTRA_GAP_COUNT_RANGE
    count = int(rng.integers(low, high + 1))
    lengths = rng.uniform(*EXTRA_GAP_LENGTH_RANGE_DAYS, size=count)
    starts = rng.uniform(0.0, SECTOR_DAYS - lengths)
    return tuple(
        (float(start), float(start + length))
        for start, length in sorted(zip(starts, lengths, strict=True))
    )


def observed_mask(time: NDArray[np.float64], gaps: tuple[Gap, ...]) -> NDArray[np.bool_]:
    """True for each time stamp that falls outside every gap."""
    observed = np.ones(time.shape, dtype=np.bool_)
    for start, end in gaps:
        observed &= ~((time >= start) & (time < end))
    return observed


def make_time_grid(rng: np.random.Generator, *, extra_gaps: bool) -> TimeGrid:
    """Build the sector's time grid with the downlink gap and, optionally, extra random gaps.

    ``rng`` should be the generator's dedicated gaps stream. It is only used when
    ``extra_gaps`` is True, so the grid without extra gaps is the same for every seed.
    """
    time = full_time_grid()
    gaps: tuple[Gap, ...] = ((DOWNLINK_GAP_START, DOWNLINK_GAP_END),)
    if extra_gaps:
        gaps += draw_extra_gaps(rng)
    return TimeGrid(time=time, observed=observed_mask(time, gaps), gaps=gaps)
