"""Pipeline settings: one validated, immutable model per step (spec 3.1).

Every setting has a default and bounds, so the app can show it as a control and re-run a step
with new values. The bounds only reject values that make no sense; they do not pick a method.
Add settings here as your methods need them, always with a default, a unit in the name and a
description.
"""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

SECTOR_HALF_LENGTH_DAYS = 13.7
"""Half of a 27.4-day TESS sector: the longest period that can show two transits."""


class _FrozenSettings(BaseModel):
    """Base for all settings: immutable, no unknown fields, no NaN or infinity."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)


class DetrendSettings(_FrozenSettings):
    """Settings for removing slow stellar variability."""

    window_days: float = Field(
        default=0.75,
        gt=0.0,
        le=5.0,
        description="Timescale in days that separates slow variability (removed) from short "
        "signals such as transits (kept).",
    )


class SearchSettings(_FrozenSettings):
    """Settings for the box least squares (BLS) period search."""

    min_period_days: float = Field(
        default=0.5, gt=0.0, description="Shortest trial period, in days."
    )
    max_period_days: float = Field(
        default=SECTOR_HALF_LENGTH_DAYS, gt=0.0, description="Longest trial period, in days."
    )
    durations_days: tuple[float, ...] = Field(
        default=(0.04, 0.08, 0.16, 0.24),
        min_length=1,
        description="Trial transit durations, in days (decision 20).",
    )

    @model_validator(mode="after")
    def _check_ranges(self) -> Self:
        if self.min_period_days >= self.max_period_days:
            raise ValueError("min_period_days must be less than max_period_days")
        if any(d <= 0 for d in self.durations_days):
            raise ValueError("every trial duration must be positive")
        if max(self.durations_days) >= self.min_period_days:
            raise ValueError("the longest trial duration must be shorter than min_period_days")
        return self


class FoldSettings(_FrozenSettings):
    """Settings for folding and binning the light curve."""

    bin_width_minutes: float = Field(
        default=10.0,
        gt=0.0,
        le=120.0,
        description="Width of each bin of the folded light curve, in minutes.",
    )


class FitSettings(_FrozenSettings):
    """Settings for the transit model fit. None yet; add them when your fit needs them."""


class VetSettings(_FrozenSettings):
    """Settings for the vetting tests."""

    snr_threshold: float = Field(
        default=7.0,
        gt=0.0,
        le=100.0,
        description="Smallest SNR (spec 3.2 definition) a planet candidate may have.",
    )


class PipelineSettings(_FrozenSettings):
    """All step settings together. ``PipelineSettings()`` gives every default."""

    detrend: DetrendSettings = DetrendSettings()
    search: SearchSettings = SearchSettings()
    fold: FoldSettings = FoldSettings()
    fit: FitSettings = FitSettings()
    vet: VetSettings = VetSettings()
