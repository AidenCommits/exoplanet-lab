"""Tests for the pipeline step settings."""

import pytest
from pydantic import ValidationError

from exoplanet_lab.pipeline.settings import (
    DetrendSettings,
    PipelineSettings,
    SearchSettings,
    VetSettings,
)


def test_defaults_are_valid() -> None:
    settings = PipelineSettings()
    assert settings.vet.snr_threshold == 7.0  # spec 3.1
    assert settings.search.durations_days == (0.04, 0.08, 0.16, 0.24)  # decision 20


def test_settings_are_frozen() -> None:
    with pytest.raises(ValidationError):
        DetrendSettings().window_days = 2.0  # type: ignore[misc]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"min_period_days": 5.0, "max_period_days": 2.0},
        {"durations_days": ()},
        {"durations_days": (0.1, -0.05)},
        {"min_period_days": 0.2, "durations_days": (0.1, 0.24)},
    ],
)
def test_search_rejects_impossible_ranges(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        SearchSettings.model_validate(kwargs)


@pytest.mark.parametrize("window", [0.0, -1.0, float("nan"), 10.0])
def test_detrend_rejects_bad_windows(window: float) -> None:
    with pytest.raises(ValidationError):
        DetrendSettings(window_days=window)


def test_json_schema_gives_the_app_defaults_and_bounds() -> None:
    # The app builds its controls from this schema (spec 3.1: every setting adjustable).
    schema = PipelineSettings.model_json_schema()
    vet = schema["$defs"]["VetSettings"]["properties"]["snr_threshold"]
    assert vet["default"] == 7.0
    assert vet["exclusiveMinimum"] == 0.0
    assert "description" in vet


def test_round_trips_through_json() -> None:
    settings = PipelineSettings(vet=VetSettings(snr_threshold=8.5))
    assert PipelineSettings.model_validate_json(settings.model_dump_json()) == settings
