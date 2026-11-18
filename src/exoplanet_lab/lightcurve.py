"""The observed light curve: the only data the analysis pipeline ever receives.

This module sits outside both the generator and the pipeline so the pipeline can use the type
without importing the generator, which holds the hidden truth (spec 2.5, blind mode). The same
type will carry real TESS data in Phase 6.
"""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]
"""A 1-D array of float64 values."""

BoolArray = NDArray[np.bool_]
"""A 1-D array of booleans."""

IntArray = NDArray[np.int64]
"""A 1-D array of int64 values."""


@dataclass(frozen=True)
class LightCurve:
    """The observed data only, exactly what a pipeline sees. Arrays share one length."""

    time: FloatArray
    """Time stamps in days from the start of the sector, increasing."""
    flux: FloatArray
    """Relative flux, normalized to a median of 1."""
    flux_err: FloatArray
    """1σ uncertainty of each flux point, in the same relative units as ``flux``."""
