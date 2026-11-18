"""Step 1, detrend: remove slow stellar variability (spec 3.1).

Written by the owner. This file fixes only the interface the app and the tests rely on.
"""

from dataclasses import dataclass

from exoplanet_lab.lightcurve import BoolArray, FloatArray, LightCurve
from exoplanet_lab.pipeline.settings import DetrendSettings


@dataclass(frozen=True)
class DetrendResult:
    """The light curve with slow variability removed, plus what the app needs to chart it.

    All arrays have one entry per observed point, in the input's order.
    """

    time: FloatArray
    """Time stamps in days, the same as the input's."""
    raw_flux: FloatArray
    """The input flux, unchanged."""
    trend: FloatArray
    """The estimated slow variability, in the input's flux units (around 1)."""
    flux: FloatArray
    """Detrended relative flux: around 1 out of transit, with short signals such as transits
    kept."""
    flux_err: FloatArray
    """1σ uncertainty of each detrended flux point."""
    excluded: BoolArray
    """True for points left out when estimating the trend (for example, masked or clipped)."""


def detrend(
    light_curve: LightCurve,
    settings: DetrendSettings,
    *,
    mask: BoolArray | None = None,
) -> DetrendResult:
    """Remove slow stellar variability from a light curve.

    Args:
        light_curve: the observed data (no truth).
        settings: detrending settings.
        mask: optional, one entry per point; True marks points that must not influence the
            trend (for example, known transits on a second pass). None means no mask.

    Returns:
        The detrended light curve and its trend.
    """
    raise NotImplementedError
