"""Tests for the result contract's rules (spec 3.2)."""

import pytest
from pydantic import ValidationError

from exoplanet_lab.pipeline.contract import (
    Candidate,
    Measurement,
    PipelineResult,
    Verdict,
    VettingFlag,
    VettingTest,
)
from exoplanet_lab.pipeline.settings import PipelineSettings


def measured(value: float) -> Measurement:
    return Measurement(value=value, uncertainty=value * 0.01)


CANDIDATE = Candidate(
    period_days=measured(3.0),
    t0_days=measured(1.2),
    duration_days=measured(0.12),
    depth=measured(0.004),
    radius_ratio=measured(0.06),
    snr=25.0,
)

ALL_FLAGS = tuple(
    VettingFlag(test=test, passed=True, value=1.0, threshold=2.0) for test in VettingTest
)


def result(
    verdict: Verdict,
    candidate: Candidate | None,
    vetting: tuple[VettingFlag, ...],
) -> PipelineResult:
    return PipelineResult(
        verdict=verdict, candidate=candidate, vetting=vetting, settings=PipelineSettings()
    )


@pytest.mark.parametrize("verdict", list(Verdict))
def test_a_candidate_can_have_any_verdict(verdict: Verdict) -> None:
    assert result(verdict, CANDIDATE, ALL_FLAGS).verdict is verdict


def test_no_candidate_means_no_planet_and_no_flags() -> None:
    assert result(Verdict.NO_PLANET, None, ()).candidate is None


@pytest.mark.parametrize("verdict", [Verdict.PLANET, Verdict.ECLIPSING_BINARY])
def test_no_candidate_rejects_other_verdicts(verdict: Verdict) -> None:
    with pytest.raises(ValidationError, match="verdict must be no_planet"):
        result(verdict, None, ())


def test_no_candidate_rejects_flags() -> None:
    with pytest.raises(ValidationError, match="no vetting flags"):
        result(Verdict.NO_PLANET, None, ALL_FLAGS)


def test_a_candidate_needs_every_flag_once() -> None:
    with pytest.raises(ValidationError, match="exactly one flag per vetting test"):
        result(Verdict.PLANET, CANDIDATE, ALL_FLAGS[:-1])
    with pytest.raises(ValidationError, match="exactly one flag per vetting test"):
        result(Verdict.PLANET, CANDIDATE, (*ALL_FLAGS, ALL_FLAGS[0]))


def test_a_test_that_could_not_run_is_allowed() -> None:
    skipped = VettingFlag(
        test=VettingTest.SECONDARY_ECLIPSE, passed=None, value=None, threshold=None
    )
    flags = (*ALL_FLAGS[:2], skipped, *ALL_FLAGS[3:])
    assert result(Verdict.PLANET, CANDIDATE, flags).vetting[2].passed is None


def test_uncertainty_may_be_missing_but_not_negative_or_nan() -> None:
    assert Measurement(value=1.0, uncertainty=None).uncertainty is None
    with pytest.raises(ValidationError):
        Measurement(value=1.0, uncertainty=-0.1)
    with pytest.raises(ValidationError):
        Measurement(value=float("nan"), uncertainty=0.1)


def test_result_round_trips_through_json() -> None:
    original = result(Verdict.PLANET, CANDIDATE, ALL_FLAGS)
    assert PipelineResult.model_validate_json(original.model_dump_json()) == original
