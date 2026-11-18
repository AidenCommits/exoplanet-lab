"""Tests for the pipeline test fixtures themselves."""

import numpy as np
from scenario_library import ScenarioLibrary

from exoplanet_lab.generator.settings import Preset, ScenarioType, TrapKind
from exoplanet_lab.lightcurve import LightCurve


def test_scenarios_are_cached(library: ScenarioLibrary) -> None:
    assert library.get(Preset.EASY, 0) is library.get(Preset.EASY, 0)
    assert library.get(Preset.EASY, 0) is not library.get(Preset.EASY, 0, spots=False)


def test_twins_differ_only_by_starspots(library: ScenarioLibrary) -> None:
    (seed,) = library.seeds(Preset.HARD, 1, scenario_type=ScenarioType.PLANET)
    twin = library.twin(Preset.HARD, seed)
    np.testing.assert_array_equal(twin.spotted.time, twin.quiet.time)
    np.testing.assert_array_equal(twin.spotted.model_flux, twin.quiet.model_flux)
    assert twin.quiet.answer_key.star.activity_amplitude == 0.0
    assert twin.spotted.answer_key.star.activity_amplitude > 0.0
    # Hard spots (0.5-2 %) dwarf the white noise, so the two fluxes differ visibly.
    assert np.ptp(twin.spotted.flux - twin.quiet.flux) > 0.003


def test_seed_filters(library: ScenarioLibrary) -> None:
    for seed in library.seeds(Preset.MEDIUM, 3, scenario_type=ScenarioType.NO_PLANET):
        assert library.get(Preset.MEDIUM, seed).answer_key.type is ScenarioType.NO_PLANET
    for seed in library.seeds(Preset.TRAP, 2, trap_kinds={TrapKind.ALIAS_GAP}):
        assert library.get(Preset.TRAP, seed).answer_key.trap_kind is TrapKind.ALIAS_GAP


def test_light_curve_carries_no_truth(library: ScenarioLibrary) -> None:
    curve = library.get(Preset.EASY, 0).light_curve
    assert type(curve) is LightCurve
    assert set(vars(curve)) == {"time", "flux", "flux_err"}
