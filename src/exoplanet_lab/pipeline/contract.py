"""The result contract: what the pipeline returns for one light curve (spec 3.2).

Scoring (spec 4.1) compares a :class:`PipelineResult` with the scenario's answer key, so every
field here uses the same definitions as the answer key. The key rules, from the spec and
decisions 21-24:

- ``depth`` is the fitted model's dip at mid-transit, the same definition as the answer key.
- ``candidate`` is None only when no signal was fitted; then the verdict is ``no_planet`` and
  there are no vetting flags.
- ``snr`` follows the single definition in spec 3.2.
"""

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from exoplanet_lab.pipeline.settings import PipelineSettings


class _FrozenRecord(BaseModel):
    """Base for contract records: immutable, no unknown fields, no NaN or infinity."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)


class Verdict(StrEnum):
    """What the pipeline concludes the light curve contains (spec 2.1 types)."""

    PLANET = "planet"
    NO_PLANET = "no_planet"
    ECLIPSING_BINARY = "eclipsing_binary"


class VettingTest(StrEnum):
    """The vetting tests of spec 3.1. Each appears exactly once when there is a candidate."""

    SNR = "snr"
    ODD_EVEN = "odd_even"
    SECONDARY_ECLIPSE = "secondary_eclipse"
    SHAPE = "shape"
    PHYSICAL = "physical"


class Measurement(_FrozenRecord):
    """A measured value with its 1σ uncertainty."""

    value: float
    uncertainty: float | None = Field(
        ge=0.0,
        description="1σ uncertainty in the value's units. None when the fit could not "
        "estimate it; scoring then counts the true value as outside both 1σ and 2σ.",
    )


class Candidate(_FrozenRecord):
    """The transit-like signal the pipeline fitted, whatever its verdict."""

    period_days: Measurement
    t0_days: Measurement = Field(
        description="Mid-time of any one transit, in days on the light curve's time axis. "
        "Scoring shifts it by whole periods to the nearest true mid-transit."
    )
    duration_days: Measurement = Field(
        description="Total duration T14 (first to last contact) of the fitted model, in days."
    )
    depth: Measurement = Field(
        description="Dip of the fitted noise-free model at mid-transit, 1 − model(t0), as a "
        "fraction of the out-of-transit flux. Not the BLS box depth, not (Rₚ/R★)²."
    )
    radius_ratio: Measurement = Field(description="Rₚ/R★ from the fit.")
    snr: float = Field(description="Signal-to-noise ratio as defined in spec 3.2.")


class VettingFlag(_FrozenRecord):
    """The outcome of one vetting test."""

    test: VettingTest
    passed: bool | None = Field(
        description="True if the candidate passed, False if it failed, None if the test could "
        "not be run (for example, no data at the phase it needs)."
    )
    value: float | None = Field(description="The measured value; None if the test did not run.")
    threshold: float | None = Field(
        description="The value the measurement was compared with; None if not applicable."
    )
    note: str = Field(
        default="",
        max_length=200,
        description="One short line for the app: what the value means and its unit.",
    )


class PipelineResult(_FrozenRecord):
    """The pipeline's answer for one light curve (spec 3.2)."""

    verdict: Verdict
    candidate: Candidate | None = Field(
        description="The fitted signal, or None when no signal was fitted."
    )
    vetting: tuple[VettingFlag, ...] = Field(
        description="One flag per vetting test when there is a candidate; empty otherwise."
    )
    settings: PipelineSettings = Field(description="The settings this result was made with.")

    @model_validator(mode="after")
    def _check_consistency(self) -> Self:
        if self.candidate is None:
            if self.verdict is not Verdict.NO_PLANET:
                raise ValueError("without a candidate the verdict must be no_planet")
            if self.vetting:
                raise ValueError("without a candidate there are no vetting flags")
            return self
        tests = [flag.test.value for flag in self.vetting]
        if sorted(tests) != sorted(t.value for t in VettingTest):
            expected = [t.value for t in VettingTest]
            raise ValueError(
                f"a candidate needs exactly one flag per vetting test {expected}, got {tests}"
            )
        return self
