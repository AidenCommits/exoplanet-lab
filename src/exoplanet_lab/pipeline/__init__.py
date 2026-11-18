"""The owner's analysis pipeline: detrend → search → fold → fit → vet (spec 3).

Each step is a pure function of the previous step's output and its own settings: no file
access, no randomness without a fixed seed, and no access to the generator or its answer key.
The input is a :class:`~exoplanet_lab.lightcurve.LightCurve`, so the same code runs on real
TESS data.
"""

from exoplanet_lab.pipeline.contract import (
    Candidate,
    Measurement,
    PipelineResult,
    Verdict,
    VettingFlag,
    VettingTest,
)
from exoplanet_lab.pipeline.detrend import DetrendResult, detrend
from exoplanet_lab.pipeline.fit import FitResult, fit
from exoplanet_lab.pipeline.fold import FoldResult, fold
from exoplanet_lab.pipeline.run import PipelineRun, run_pipeline
from exoplanet_lab.pipeline.search import BlsPeak, SearchResult, search
from exoplanet_lab.pipeline.settings import (
    DetrendSettings,
    FitSettings,
    FoldSettings,
    PipelineSettings,
    SearchSettings,
    VetSettings,
)
from exoplanet_lab.pipeline.vet import VetResult, vet

__all__ = [
    "BlsPeak",
    "Candidate",
    "DetrendResult",
    "DetrendSettings",
    "FitResult",
    "FitSettings",
    "FoldResult",
    "FoldSettings",
    "Measurement",
    "PipelineResult",
    "PipelineRun",
    "PipelineSettings",
    "SearchResult",
    "SearchSettings",
    "Verdict",
    "VetResult",
    "VetSettings",
    "VettingFlag",
    "VettingTest",
    "detrend",
    "fit",
    "fold",
    "run_pipeline",
    "search",
    "vet",
]
