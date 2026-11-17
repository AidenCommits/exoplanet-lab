"""Tests for saving and loading scenarios."""

import json
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from pydantic import ValidationError

from exoplanet_lab.generator.presets import generate_preset_scenario
from exoplanet_lab.generator.scenario import Scenario, generate_scenario
from exoplanet_lab.generator.settings import Preset
from exoplanet_lab.generator.storage import (
    LIGHT_CURVE_COLUMNS,
    light_curve_scenario_id,
    load_answer_key,
    load_light_curve,
    save_scenario,
    scenario_files,
)


@pytest.fixture(scope="module")
def scenario() -> Scenario:
    return generate_preset_scenario(Preset.MEDIUM, 7)


def assert_same_light_curve(scenario: Scenario, path: Path) -> None:
    loaded = load_light_curve(path)
    np.testing.assert_array_equal(loaded.time, scenario.time)
    np.testing.assert_array_equal(loaded.flux, scenario.flux)
    np.testing.assert_array_equal(loaded.flux_err, scenario.flux_err)


def test_round_trip_is_exact(scenario: Scenario, tmp_path: Path) -> None:
    files = save_scenario(scenario, tmp_path)
    assert files == scenario_files(tmp_path, scenario.answer_key.scenario_id)
    assert_same_light_curve(scenario, files.light_curve)
    assert load_answer_key(files.answer_key) == scenario.answer_key


def test_light_curve_holds_no_truth(scenario: Scenario, tmp_path: Path) -> None:
    files = save_scenario(scenario, tmp_path)
    schema = pq.read_schema(files.light_curve)
    assert tuple(schema.names) == LIGHT_CURVE_COLUMNS
    assert all(schema.field(name).type == pa.float64() for name in LIGHT_CURVE_COLUMNS)
    # Only the scenario ID may ride along in the metadata, nothing from the answer key.
    assert set(schema.metadata or {}) == {b"scenario_id"}
    assert light_curve_scenario_id(files.light_curve) == scenario.answer_key.scenario_id


def test_answer_key_is_readable_json(scenario: Scenario, tmp_path: Path) -> None:
    files = save_scenario(scenario, tmp_path)
    data = json.loads(files.answer_key.read_text(encoding="utf-8"))
    assert data["scenario_id"] == scenario.answer_key.scenario_id
    assert data["preset"] == "medium"


def test_saved_key_regenerates_the_saved_light_curve(scenario: Scenario, tmp_path: Path) -> None:
    files = save_scenario(scenario, tmp_path)
    rebuilt = generate_scenario(load_answer_key(files.answer_key).settings)
    assert_same_light_curve(rebuilt, files.light_curve)


def test_saving_twice_overwrites_cleanly(scenario: Scenario, tmp_path: Path) -> None:
    save_scenario(scenario, tmp_path)
    files = save_scenario(scenario, tmp_path)
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted(
        [files.light_curve.name, files.answer_key.name]
    )
    assert_same_light_curve(scenario, files.light_curve)


def test_save_creates_missing_directory(scenario: Scenario, tmp_path: Path) -> None:
    files = save_scenario(scenario, tmp_path / "a" / "b")
    assert files.light_curve.is_file() and files.answer_key.is_file()


def test_missing_files_raise(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_light_curve(tmp_path / "nope.parquet")
    with pytest.raises(FileNotFoundError):
        load_answer_key(tmp_path / "nope.json")


def test_invalid_answer_key_raises(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text('{"scenario_id": "abc"}', encoding="utf-8")
    with pytest.raises(ValidationError):
        load_answer_key(path)


def test_wrong_columns_raise(tmp_path: Path) -> None:
    path = tmp_path / "bad.parquet"
    pq.write_table(pa.table({"time": [0.0], "flux": [1.0]}), path)
    with pytest.raises(ValueError, match="columns"):
        load_light_curve(path)


def test_wrong_column_type_raises(tmp_path: Path) -> None:
    path = tmp_path / "bad.parquet"
    table = pa.table({"time": [0.0], "flux": [1.0], "flux_err": pa.array([1], pa.int64())})
    pq.write_table(table, path)
    with pytest.raises(ValueError, match="flux_err"):
        load_light_curve(path)
