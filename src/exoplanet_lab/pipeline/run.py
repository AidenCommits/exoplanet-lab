"""The whole pipeline: light curve in, result contract out (spec 3).

Written by the owner. This file fixes only the interface the app and the tests rely on.
"""

from dataclasses import dataclass

from exoplanet_lab.lightcurve import LightCurve
from exoplanet_lab.pipeline.contract import PipelineResult
from exoplanet_lab.pipeline.detrend import DetrendResult
from exoplanet_lab.pipeline.fit import FitResult
from exoplanet_lab.pipeline.fold import FoldResult
from exoplanet_lab.pipeline.search import SearchResult
from exoplanet_lab.pipeline.settings import PipelineSettings
from exoplanet_lab.pipeline.vet import VetResult


@dataclass(frozen=True)
class PipelineRun:
    """Every step's output plus the final result, so the app can chart each step.

    A step's output is None when the pipeline stopped before reaching it; then
    ``result.candidate`` is None too.
    """

    detrend: DetrendResult
    search: SearchResult
    fold: FoldResult | None
    fit: FitResult | None
    vet: VetResult | None
    result: PipelineResult


def run_pipeline(light_curve: LightCurve, settings: PipelineSettings) -> PipelineRun:
    """Run every step on one light curve.

    Args:
        light_curve: the observed data (no truth).
        settings: settings for every step.

    Returns:
        Each step's output and the result contract.
    """
    raise NotImplementedError
