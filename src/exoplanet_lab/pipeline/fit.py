"""Step 4, fit: fit a batman transit model to the candidate (spec 3.1).

Written by the owner. This file fixes only the interface the app and the tests rely on.
"""

from dataclasses import dataclass

from exoplanet_lab.lightcurve import FloatArray
from exoplanet_lab.pipeline.contract import Measurement
from exoplanet_lab.pipeline.detrend import DetrendResult
from exoplanet_lab.pipeline.fold import FoldResult
from exoplanet_lab.pipeline.settings import FitSettings


@dataclass(frozen=True)
class FitResult:
    """Best-fit transit parameters with 1σ uncertainties, and the model for charting.

    Parameter definitions match the result contract (``contract.Candidate``).
    """

    period_days: Measurement
    t0_days: Measurement
    """Mid-time of one transit, in days on the light curve's time axis."""
    duration_days: Measurement
    """Total duration T14 of the fitted model, in days."""
    depth: Measurement
    """Fitted model's dip at mid-transit, 1 − model(t0)."""
    radius_ratio: Measurement
    """Rₚ/R★."""
    a_over_rstar: Measurement
    """Semi-major axis over stellar radius."""
    impact_parameter: Measurement
    """Impact parameter b, in stellar radii."""
    model_phase_days: FloatArray
    """A fine grid of times from mid-transit, in days, increasing, for drawing the model."""
    model_flux: FloatArray
    """The best-fit model at ``model_phase_days``; same length."""
    residuals: FloatArray
    """Data minus best-fit model at each point of ``FoldResult.flux``; same length and order."""
    reduced_chi_square: float
    """χ² of the fit divided by its degrees of freedom; about 1 for a good fit."""


def fit(detrended: DetrendResult, folded: FoldResult, settings: FitSettings) -> FitResult:
    """Fit a transit model to the detrended data around the folded candidate.

    Args:
        detrended: output of the detrend step.
        folded: output of the fold step; gives the candidate's period and t0.
        settings: fit settings.

    Returns:
        Best-fit parameters with uncertainties, the model curve and the residuals.
    """
    raise NotImplementedError
