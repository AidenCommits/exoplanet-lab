# Decisions log

Newest first. Each entry says what was decided and why. Details live in `docs/spec.md`.

## 2026-11-16: Phase 3 data generator

| # | Decision | Why |
| --- | --- | --- |
| 1 | Use a `src/` layout (`src/exoplanet_lab/`) built with the `uv_build` backend. | Tests and notebooks import the installed package, not loose files. |
| 2 | Presets target an **expected-SNR range** and solve for the noise level, instead of drawing radius and noise independently. Easy 20–200 (log-uniform), Medium 10–20, Hard 6–10. | SNR controls difficulty directly. Solving for noise has an exact answer; solving for radius doesn't, because of limb darkening. |
| 3 | Easy is planet-only with ≥ 4 transits; Medium and Hard are 70 % planet / 30 % no_planet; every non-Trap preset needs ≥ 3 transits. | Matches the spec's intent with a stated mix ratio. |
| 4 | Medium planet radius is 2.5–5 R⊕ (was 3–6). | Larger planets at SNR 10–20 would need noise above the 3000 ppm cap. |
| 5 | `no_planet` scenarios use a discarded "phantom" planet to set their noise. | Otherwise the noise level alone would hint at the answer. |
| 6 | Trap has six kinds: `near_equal_eb`, `spot_only`, `grazing_planet`, `two_transit`, `alias_gap`, `classic_eb`. | The spec listed five; `classic_eb` was added so binaries aren't only ever the near-equal kind. |
| 7 | `alias_gap` means the middle of three transits falls in the mid-sector gap. | Turns the spec's vague "alias-prone periods" into a case where 2P is a true alias. |
| 8 | Answer key gains `trap_kind` and `expected_snr`; blind mode hides them with the rest of the key. | Batch scoring (Phase 6) breaks results down by trap kind and by SNR. |
| 9 | Quadratic limb-darkening coefficients come from a small table based on Claret (2017), applied by batman. | batman computes the model but doesn't supply coefficients. |
| 10 | The planted-transit recovery test does both checks: (a) fold at the true ephemeris and measure the depth, and (b) run astropy's `BoxLeastSquares` with default settings and recover the period within 1 %. | (b) checks the generator only; it is not pipeline code. |
| 11 | The decisions log is this Markdown file, replacing the empty `decisions.docx.docx`. | Plain text shows clean diffs in git. |
| 12 | Add `setuptools` as a dependency. | batman 2.5.x imports `distutils`, which Python 3.12+ removed; setuptools provides a stand-in. Remove it once batman is fixed. |
| 13 | The Python environment lives outside OneDrive, at `%USERPROFILE%\.venvs\exoplanet-lab`, set with the user-level variable `UV_PROJECT_ENVIRONMENT`. The old in-repo `.venv` was deleted. `setup.ps1` sets this up automatically when the repo is inside OneDrive. | OneDrive locked files inside `.venv`, so `uv sync` kept failing with "Access is denied". Details, checks and how to undo it: README.md, "Python environment location". |
| 14 | A transit counts as observed when at least 50 % of its points (duration ÷ cadence) fall outside the gaps and inside the sector. | A sliver at a gap edge doesn't help confirm a period. Measuring against the full duration treats sector edges and gaps the same way. |
| 15 | Each seed is split into fixed, numbered random streams (preset, gaps, activity, noise) with `SeedSequence(seed, spawn_key=(n,))`. | Changing one part of the generator never shifts the random draws of another. Stream numbers must never change. |
| 16 | Flux and `flux_err` are divided by the median of the observed raw flux. The answer-key depth is the noise-free model depth. `scenario_id` is the first 12 hex characters of the settings' SHA-256 hash. | Spec 2.2 needs a median of 1, and the rescaling changes depth by only about 10⁻⁴. A hash ID makes identical settings give an identical ID. |
