"""Saving and loading scenarios (spec 2.6).

Each scenario is two files with the same base name:

- ``<scenario_id>.parquet``: the light curve, with columns ``time``, ``flux`` and ``flux_err``.
- ``<scenario_id>.json``: the answer key.

The light-curve file holds no truth at all, so in blind mode the app can serve it without ever
opening the answer key. The noise-free model is not saved; it can be regenerated from the
settings in the answer key. Generated files are not committed (regenerate them from the seed).
"""

import os
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from exoplanet_lab.generator.answer_key import AnswerKey
from exoplanet_lab.generator.scenario import LightCurve, Scenario

LIGHT_CURVE_COLUMNS = ("time", "flux", "flux_err")
"""The Parquet columns, in order (spec 2.6)."""

SCENARIO_ID_METADATA_KEY = b"scenario_id"
"""Parquet metadata key that links a light curve to its answer key. It is not a truth value."""


@dataclass(frozen=True)
class ScenarioFiles:
    """Where one scenario's files are."""

    light_curve: Path
    answer_key: Path


def scenario_files(directory: Path, scenario_id: str) -> ScenarioFiles:
    """The two file paths for a scenario ID inside ``directory``."""
    return ScenarioFiles(
        light_curve=directory / f"{scenario_id}.parquet",
        answer_key=directory / f"{scenario_id}.json",
    )


def _write_atomically(path: Path, write: Callable[[Path], object]) -> None:
    """Write to a temporary file in the same folder, then rename it over ``path``.

    A reader (or a sync client such as OneDrive) then sees either the old file or the complete
    new one, never a half-written file.
    """
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        write(tmp)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def save_scenario(scenario: Scenario, directory: Path) -> ScenarioFiles:
    """Save a scenario's light curve and answer key into ``directory``, creating it if needed.

    Saving the same scenario again overwrites its files; identical settings always give
    identical files.
    """
    directory.mkdir(parents=True, exist_ok=True)
    key = scenario.answer_key
    files = scenario_files(directory, key.scenario_id)

    curve = scenario.light_curve
    table = pa.table(
        {name: pa.array(getattr(curve, name), type=pa.float64()) for name in LIGHT_CURVE_COLUMNS}
    ).replace_schema_metadata({SCENARIO_ID_METADATA_KEY: key.scenario_id.encode("utf-8")})
    _write_atomically(files.light_curve, lambda tmp: pq.write_table(table, tmp))

    key_json = key.model_dump_json(indent=2) + "\n"
    _write_atomically(files.answer_key, lambda tmp: tmp.write_text(key_json, encoding="utf-8"))
    return files


def load_light_curve(path: Path) -> LightCurve:
    """Read a light curve saved by :func:`save_scenario`.

    Raises:
        FileNotFoundError: if the file does not exist.
        ValueError: if the file does not have exactly the light-curve columns as float64.
    """
    if not path.is_file():
        raise FileNotFoundError(f"no light curve at {path}")
    table = pq.read_table(path)
    if tuple(table.column_names) != LIGHT_CURVE_COLUMNS:
        raise ValueError(
            f"{path.name} has columns {table.column_names}, expected {list(LIGHT_CURVE_COLUMNS)}"
        )
    arrays = {}
    for name in LIGHT_CURVE_COLUMNS:
        column = table.column(name)
        if column.type != pa.float64():
            raise ValueError(f"{path.name}: column {name!r} is {column.type}, expected double")
        arrays[name] = np.asarray(column.to_numpy(), dtype=np.float64)
    return LightCurve(**arrays)


def light_curve_scenario_id(path: Path) -> str | None:
    """The scenario ID stored in a light curve's metadata, or None if it has none."""
    metadata = pq.read_schema(path).metadata or {}
    value = metadata.get(SCENARIO_ID_METADATA_KEY)
    return value.decode("utf-8") if value is not None else None


def load_answer_key(path: Path) -> AnswerKey:
    """Read and validate an answer key saved by :func:`save_scenario`.

    Raises:
        FileNotFoundError: if the file does not exist.
        pydantic.ValidationError: if the file is not a valid answer key.
    """
    if not path.is_file():
        raise FileNotFoundError(f"no answer key at {path}")
    return AnswerKey.model_validate_json(path.read_text(encoding="utf-8"))
