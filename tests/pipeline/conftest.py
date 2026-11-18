"""Shared fixtures for pipeline tests."""

import pytest
from scenario_library import ScenarioLibrary


@pytest.fixture(scope="session")
def library() -> ScenarioLibrary:
    """One scenario cache shared by every pipeline test."""
    return ScenarioLibrary()
