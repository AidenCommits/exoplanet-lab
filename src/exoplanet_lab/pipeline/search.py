"""Step 2, search: find the strongest periodic box-shaped dip with BLS (spec 3.1).

Written by the owner. This file fixes only the interface the app and the tests rely on.
"""

from dataclasses import dataclass

from exoplanet_lab.lightcurve import FloatArray
from exoplanet_lab.pipeline.detrend import DetrendResult
from exoplanet_lab.pipeline.settings import SearchSettings


@dataclass(frozen=True)
class BlsPeak:
    """One peak of the BLS periodogram: the best box model at that period."""

    period_days: float
    t0_days: float
    """Mid-time of one box (one transit), in days on the light curve's time axis."""
    duration_days: float
    depth: float
    """Box depth: mean out-of-box flux minus mean in-box flux (relative flux)."""
    power: float
    """The periodogram value at this period, in the units of ``SearchResult.power``."""


@dataclass(frozen=True)
class SearchResult:
    """The periodogram and its strongest peaks."""

    periods_days: FloatArray
    """Trial periods, in days, increasing."""
    power: FloatArray
    """Periodogram value at each trial period; same length as ``periods_days``."""
    best: BlsPeak
    """The strongest peak."""
    other_peaks: tuple[BlsPeak, ...]
    """Further distinct peaks in decreasing power, for charting aliases. May be empty."""


def search(detrended: DetrendResult, settings: SearchSettings) -> SearchResult:
    """Run a BLS period search on detrended data.

    Args:
        detrended: output of the detrend step.
        settings: period range and trial durations.

    Returns:
        The periodogram, its best peak and other notable peaks.
    """
    raise NotImplementedError
