# exoplanet-lab v1 spec

Status: **draft for review** (Nov 15, 2026). Decisions marked *(proposed)* still need the owner's OK.

## 1. Goal

A local app that generates realistic, TESS-like light curves with a hidden answer, lets the owner run
their own analysis pipeline on them, and scores the result. v1 covers one scenario family:
exoplanet transits, plus the impostors that mimic them.

## 2. Scenarios

### 2.1 Scenario types
| Type | What's in the light curve | What a correct pipeline should say |
| --- | --- | --- |
| `planet` | One transiting planet, plus noise and optional star activity | Planet, with period, depth and size |
| `no_planet` | A quiet or spotty star, no transits | No planet |
| `eclipsing_binary` | Two stars eclipsing each other (deep primary + shallower secondary eclipse) | Not a planet |

One planet at most per star in v1.

### 2.2 Data style (TESS-like)
- Cadence: 2 minutes (720 points per day).
- Baseline: one ~27.4-day sector, with a ~1-day data gap in the middle (TESS downlink gap).
- Optional extra random gaps (a setting).
- Time in days starting near 0; flux normalized to a median of 1; each point has a flux error.

### 2.3 Generator settings and ranges
| Setting | Range | Notes |
| --- | --- | --- |
| Random seed | integer | Same seed + settings = identical scenario |
| Star radius | 0.5–1.5 R☉ | Star mass derived from a simple main-sequence relation |
| Planet radius | 0.8–15 R⊕ | Sets depth ≈ (Rₚ/R★)² |
| Orbital period | 0.5–13.5 days | ≥ 2 transits in the sector; presets except Trap need ≥ 3 |
| Impact parameter b | 0–0.9 (up to 1.05 in Trap) | > ~0.9 is grazing (V-shaped) |
| Limb darkening | quadratic, fixed by star type | Coefficients from Claret (2017), applied by batman |
| Orbit | circular | Eccentric orbits out of scope |
| Noise per point | 100–3000 ppm | White (random) noise |
| Star activity amplitude | 0–2 % | Starspot modulation |
| Star rotation period | 1–15 days | Activity repeats at this period, with slow amplitude drift |
| Eclipsing binary depths | primary 1–30 %; secondary 0–100 % of primary | Secondary at phase 0.5 |

Transit duration is not set directly: it follows from period, star size/mass and b (Kepler's third law).

### 2.4 Presets
Presets choose randomly within their ranges using the seed. Star radius is 0.5–1.5 R☉ in every preset.

**Difficulty is set by expected SNR, not by noise.** Each planet scenario draws a target SNR, then
solves for the noise per point: σ = depth × √N ÷ SNR, where depth comes from the noise-free model
(limb darkening included) and N is the number of observed in-transit points after gaps. If σ falls
outside 100–3000 ppm, the draw is repeated. `no_planet` scenarios in Medium and Hard go through the
same steps with a phantom planet that is then discarded, so their noise levels match the planet
scenarios and don't give the answer away. Expected SNR counts white noise only (it ignores star
activity).

| Preset | Mix | Target SNR | Rₚ (R⊕) | P (d) | b | Activity | Rotation (d) | Extra gaps | Transits |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Easy | 100 % planet | 30–200 (log-uniform) | 8–15 | 0.5–6 | 0–0.7 | 0–0.1 % | 5–15 | off | ≥ 4 |
| Medium | 70 % planet / 30 % no_planet | 10–30 | 2.5–5 | 1–9 | 0–0.8 | 0.1–0.5 % | 2–15 | 50 % chance | ≥ 3 |
| Hard | 70 % planet / 30 % no_planet | 6–10 | 0.8–3 | 1–12 | 0–0.9 | 0.5–2 % | 1–15 | 50 % chance | ≥ 3 |
| Trap | One of six kinds below, equally likely | see below | | | | | | 50 % chance | ≥ 2 |
| Custom | Owner's choice | — | All sliders available | | | | | | ≥ 2 |

The SNR ranges join up with no gaps: Hard 6–10, Medium 10–30, Easy 30–200. SNR ranges are
uniform unless marked log-uniform.

Hard's SNR range straddles the default vetting threshold of 7, so some Hard planets are expected
to be missed.

**Trap kinds** (recorded as `trap_kind` in the answer key). Noise is log-uniform in 100–3000 ppm
unless stated.

| `trap_kind` | Type | Settings | Why it's a trap |
| --- | --- | --- | --- |
| `near_equal_eb` | eclipsing_binary | Primary 1–5 %, secondary 80–100 % of primary | Folded at P/2 it looks like one planet; only an odd/even depth test catches it |
| `spot_only` | no_planet | Activity 1–2 %, rotation 1–5 d, noise 100–1000 ppm | Spot dips can give false BLS peaks |
| `grazing_planet` | planet | b 0.9–1.05, Rₚ 8–15 R⊕, SNR 15–50 | V-shaped dip that looks like a binary |
| `two_transit` | planet | P 9–13.5 d, exactly 2 observed transits, Rₚ 2–10 R⊕, SNR 10–30 | Few repeats to confirm the period |
| `alias_gap` | planet | Middle of 3 transits falls in the mid-sector gap, Rₚ 2–10 R⊕, SNR 10–30 | The 2 observed transits fit P and 2P equally well |
| `classic_eb` | eclipsing_binary | Primary 1–30 %, secondary 5–60 % of primary | Baseline binary for the secondary-eclipse test |

Trap values not listed above: binaries have P 1–9 d, b 0–0.9 and ≥ 2 observed primary eclipses;
`grazing_planet` has P 1–9 d; `alias_gap` has P 7–13.4 d so the sector holds exactly 3 transits.
Every kind except `spot_only` uses activity 0.1–0.5 % and rotation 2–15 d.

### 2.5 Answer key
Saved with every scenario, separately from the light curve:
- `scenario_id`, `seed`, `preset`, all generator settings
- `type` and `has_planet`
- For planets: period, t0 (first mid-transit time), duration, depth, Rₚ/R★, Rₚ in R⊕, a/R★, b, number of transits in the data
- For EBs: true orbital period, primary and secondary eclipse depths
- Star: radius, mass, noise level, activity amplitude and rotation period
- `trap_kind`: which Trap sub-kind produced the scenario (null outside the Trap preset)
- `expected_snr`: depth ÷ noise per point × √(observed in-transit points), white noise only
  (null when there is no planet)

**Blind mode (default on):** the app hides the answer key until the owner submits a result for that
scenario. This covers every field above, including `trap_kind` and `expected_snr`. It can be
switched off for learning and debugging.

### 2.6 Storage
- Light curve: Parquet file with columns `time`, `flux`, `flux_err`.
- Answer key: JSON file next to it.
- Generated files are not committed (regenerate from seed); see `.gitignore`.

## 3. Analysis pipeline (written by the owner)

The pipeline is the owner's code. This section only defines how the app talks to it.

### 3.1 Steps
1. **Detrend**: remove slow star variability. Setting: window length.
2. **Search (BLS)**: settings: period range, duration grid. Output: periodogram, best period, t0, duration, depth.
3. **Phase fold**: fold on the best period. Output: folded and binned data.
4. **Fit**: batman transit model fit. Output: best-fit parameters with uncertainties.
5. **Vet**: SNR, odd/even depth, secondary eclipse, shape and physical-sanity checks. Setting: SNR threshold (default 7).

Every step must return its intermediate output so the app can chart it, and every setting must be
adjustable from the app.

### 3.2 Result contract
The pipeline returns one result per scenario:
- `verdict`: `planet`, `no_planet` or `eclipsing_binary`
- If a candidate was found: period, t0, duration, depth, Rₚ/R★ (each with uncertainty), SNR
- Vetting flags (pass/fail per test, with the measured value)

## 4. Scoring

### 4.1 Per scenario
Outcome (one of):
- **Correct detection**: real planet, verdict `planet`, period matches
- **Wrong period**: real planet found but period doesn't match
- **Alias**: period off by a simple ratio (½, 2, ⅓, 3) — reported separately
- **Missed**: real planet, verdict not `planet`
- **False alarm**: no planet (or EB), verdict `planet`
- **Correct rejection**: no planet (or EB), verdict not `planet`

Match rules *(proposed)*:
- Period matches if within 1 % of the true period.
- t0 matches if within half a transit duration.

For correct detections, also report:
- Percent error in depth, Rₚ/R★ and duration
- Whether the true value falls inside the owner's 1σ and 2σ error bars

### 4.2 Batch scoring (Phase 6)
- Run the pipeline over hundreds of generated scenarios (results in Parquet, queried with DuckDB).
- Detection rate as a function of planet size, noise and expected SNR.
- False-alarm rate on `no_planet` and `eclipsing_binary` scenarios.
- Alias rate.

## 5. Screens (v1)
1. **Scenario picker**: presets, custom sliders, seed, Generate button.
2. **Raw data**: interactive light curve plot (zoom, pan).
3. **Pipeline steps**: step through detrend → BLS → fold → fit → vet; each step shows its chart and
   settings, and can be re-run with new settings.
4. **Results and score**: submit the result; then see the answer key, the outcome and the errors.
5. **Scoring dashboard** (Phase 6): batch results charts.

Visual design comes from the Phase 2 mockups.

## 6. Definition of done for v1 *(proposed)*
- Generator produces all three scenario types and all presets, reproducibly from a seed, with tests
  (including: a planted transit is recovered at low noise).
- The owner's pipeline runs as a module on any scenario and returns the result contract.
- Screens 1–4 work end to end on a local machine.
- Per-scenario scoring is correct and tested.
- Batch scoring over ≥ 500 scenarios, with the dashboard (screen 5).
- The pipeline is run on real TESS data for at least 3 known planets and compared with published values.
- Deployed, with a README showing results.

## 7. Out of scope for v1
- More than one planet per star
- Eccentric orbits
- Correlated instrument noise (momentum dumps, scattered light); only white noise + star activity
- Transit timing variations
- Blended or background eclipsing binaries
- Machine-learning classifiers
- Full MCMC fitting (uncertainties from the fit's covariance; MCMC is a possible stretch goal)
- Other scenario families (radial velocity, variable stars, galaxy rotation curves)
- User accounts and databases

## 8. Open questions
- Confirm the match rules in 4.1 (1 % period, half-duration t0).
- Confirm the definition of done in section 6.
