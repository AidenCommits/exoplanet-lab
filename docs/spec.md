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
| Limb darkening | quadratic, fixed by star type | From batman |
| Orbit | circular | Eccentric orbits out of scope |
| Noise per point | 100–3000 ppm | White (random) noise |
| Star activity amplitude | 0–2 % | Starspot modulation |
| Star rotation period | 1–15 days | Activity repeats at this period, with slow amplitude drift |
| Eclipsing binary depths | primary 1–30 %; secondary 0–100 % of primary | Secondary at phase 0.5 |

Transit duration is not set directly: it follows from period, star size/mass and b (Kepler's third law).

### 2.4 Presets
| Preset | Mix | Typical settings |
| --- | --- | --- |
| Easy | Planet | Large planet, low noise, quiet star, ≥ 4 transits |
| Medium | Planet or no_planet | Neptune-size, moderate noise, mild activity |
| Hard | Planet or no_planet | Small planet, high noise, active star |
| Trap | Any type | EBs with near-equal eclipses, spot-only stars, grazing planets, 2-transit planets, alias-prone periods |
| Custom | Owner's choice | All sliders available |

Presets choose randomly within their ranges using the seed.

### 2.5 Answer key
Saved with every scenario, separately from the light curve:
- `scenario_id`, `seed`, `preset`, all generator settings
- `type` and `has_planet`
- For planets: period, t0 (first mid-transit time), duration, depth, Rₚ/R★, Rₚ in R⊕, a/R★, b, number of transits in the data
- For EBs: true orbital period, primary and secondary eclipse depths
- Star: radius, mass, noise level, activity amplitude and rotation period

**Blind mode (default on):** the app hides the answer key until the owner submits a result for that
scenario. It can be switched off for learning and debugging.

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
