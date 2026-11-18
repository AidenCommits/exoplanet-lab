"""Step 5, vet: run the false-alarm tests and reach a verdict (spec 3.1).

Written by the owner. This file fixes only the interface the app and the tests rely on.
"""

from dataclasses import dataclass

from exoplanet_lab.pipeline.contract import Verdict, VettingFlag
from exoplanet_lab.pipeline.detrend import DetrendResult
from exoplanet_lab.pipeline.fit import FitResult
from exoplanet_lab.pipeline.fold import FoldResult
from exoplanet_lab.pipeline.settings import VetSettings


@dataclass(frozen=True)
class VetResult:
    """The vetting flags, the candidate's SNR and the verdict."""

    snr: float
    """Signal-to-noise ratio as defined in spec 3.2."""
    flags: tuple[VettingFlag, ...]
    """One flag per ``contract.VettingTest``."""
    verdict: Verdict


def vet(
    detrended: DetrendResult, folded: FoldResult, fitted: FitResult, settings: VetSettings
) -> VetResult:
    """Test whether a fitted candidate is a planet, a binary or nothing.

    Args:
        detrended: output of the detrend step.
        folded: output of the fold step (per-point phases and epochs).
        fitted: output of the fit step.
        settings: test thresholds.

    Returns:
        The SNR, one flag per vetting test, and the verdict.
    """
    raise NotImplementedError
