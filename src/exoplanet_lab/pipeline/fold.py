"""Step 3, fold: fold the light curve on a period and bin it (spec 3.1).

Written by the owner. This file fixes only the interface the app and the tests rely on.
"""

from dataclasses import dataclass

from exoplanet_lab.lightcurve import FloatArray, IntArray
from exoplanet_lab.pipeline.detrend import DetrendResult
from exoplanet_lab.pipeline.search import BlsPeak
from exoplanet_lab.pipeline.settings import FoldSettings


@dataclass(frozen=True)
class FoldResult:
    """The folded and binned light curve.

    Per-point arrays have one entry per observed point, in the input's order. Binned arrays
    have one entry per bin that contains data, in increasing phase.
    """

    period_days: float
    """The period the data were folded on, in days."""
    t0_days: float
    """The mid-transit time that phase 0 refers to, in days."""
    phase_days: FloatArray
    """Time from the nearest mid-transit, in days, in [-period/2, period/2)."""
    epoch: IntArray
    """Transit number of each point: 0 for the transit at ``t0_days``, ±1 for the next and
    previous, and so on. Lets later steps split odd and even transits."""
    flux: FloatArray
    """Detrended flux of each point."""
    flux_err: FloatArray
    """1σ uncertainty of each point."""
    bin_phase_days: FloatArray
    """Centre of each bin, in days from mid-transit."""
    bin_flux: FloatArray
    """Flux of each bin."""
    bin_flux_err: FloatArray
    """1σ uncertainty of each bin's flux."""


def fold(detrended: DetrendResult, peak: BlsPeak, settings: FoldSettings) -> FoldResult:
    """Fold detrended data on a peak's period and t0, and bin it.

    Args:
        detrended: output of the detrend step.
        peak: the BLS peak to fold on (usually ``SearchResult.best``).
        settings: bin width.

    Returns:
        Per-point phases, epochs and fluxes, plus the binned curve.
    """
    raise NotImplementedError
