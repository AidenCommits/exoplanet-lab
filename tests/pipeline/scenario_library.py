"""Generator scenarios for pipeline tests, built on demand and cached.

Tests may look at the truth (answer key, model flux, spot-free twins) to judge the pipeline's
output; the pipeline itself only ever receives ``scenario.light_curve``.
"""

from dataclasses import dataclass, field

from exoplanet_lab.generator.presets import draw_settings
from exoplanet_lab.generator.scenario import Scenario, generate_scenario
from exoplanet_lab.generator.settings import Preset, ScenarioSettings, ScenarioType, TrapKind


def without_activity(settings: ScenarioSettings) -> ScenarioSettings:
    """The same scenario on a star with no starspots.

    Every random part of the generator has its own stream (decision 15), so the noise, gaps and
    transits stay identical; only the spot signal (and the median normalization) changes.
    """
    star = settings.star.model_copy(update={"activity_amplitude": 0.0})
    return settings.model_copy(update={"star": star})


@dataclass(frozen=True)
class Twin:
    """One scenario generated twice: as drawn, and on a spot-free star."""

    spotted: Scenario
    quiet: Scenario


@dataclass
class ScenarioLibrary:
    """Generates scenarios on demand and remembers them, so each is built only once per run."""

    _cache: dict[tuple[int, bool, str], Scenario] = field(default_factory=dict)

    def get(self, preset: Preset, seed: int, *, spots: bool = True) -> Scenario:
        """The scenario a preset draws for ``seed``, optionally with its starspots removed."""
        return self.from_settings(draw_settings(preset, seed), spots=spots)

    def from_settings(self, settings: ScenarioSettings, *, spots: bool = True) -> Scenario:
        """The scenario for fully specified settings, optionally with its starspots removed."""
        key = (settings.seed, spots, settings.model_dump_json())
        if key not in self._cache:
            used = settings if spots else without_activity(settings)
            self._cache[key] = generate_scenario(used)
        return self._cache[key]

    def twin(self, preset: Preset, seed: int) -> Twin:
        """A preset scenario with and without its starspots."""
        return Twin(
            spotted=self.get(preset, seed, spots=True),
            quiet=self.get(preset, seed, spots=False),
        )

    @staticmethod
    def seeds(
        preset: Preset,
        count: int,
        *,
        scenario_type: ScenarioType | None = None,
        trap_kinds: set[TrapKind] | None = None,
    ) -> list[int]:
        """The first ``count`` seeds, from 0 upwards, whose draw matches the filters."""
        found: list[int] = []
        seed = 0
        while len(found) < count:
            settings = draw_settings(preset, seed)
            type_ok = scenario_type is None or settings.type is scenario_type
            trap_ok = trap_kinds is None or settings.trap_kind in trap_kinds
            if type_ok and trap_ok:
                found.append(seed)
            seed += 1
            if seed > 10_000:
                raise RuntimeError(f"fewer than {count} matching seeds below 10 000")
        return found
