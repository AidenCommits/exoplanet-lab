# exoplanet-lab design reference (approved Nov 16, 2026)

Mockups: https://claude.ai/artifact/6UF8iHbjcy5a8CjbqqMQH9
**Approved version: "Round 2 · editor layout (instrument console)"** (the frames named `Console-*`). Round 1 on the same canvas is kept for comparison only; do not build from it.

## Direction
A professional desktop tool in the style of a game engine or photo editor (Unity, Unreal, Blender, Photoshop, DaVinci Resolve): docked panels around a central viewport, dense UI, no decoration. Desktop and laptop first; phone layouts are not a goal.

## Typography
- UI: **JetBrains Mono** everywhere (400, 500, 700).
- Longer help sentences only: **Inter** (400, 500).
- Sizes: 12px for UI text, 11px for labels and panel headers (uppercase, 0.06em letter spacing), 16–18px for key values.

## Colors
| Token | Hex | Use |
| --- | --- | --- |
| bg | `#141414` | App background, viewport |
| panel | `#1C1C1C` | Docked panels |
| header | `#232323` | Menu bar, tab bar, panel headers, status bar |
| line | `#2E2E2E` | 1px dividers between everything |
| text | `#E3E3E3` | Main text, data points |
| muted | `#A0A0A0` | Labels, secondary text |
| accent | `#FF6A13` | The one signal color: active tab, selection, Run button, model fits, selection windows |
| pass | `#5FBF8F` | Passed checks, correct outcomes (always with ✓ and text) |
| fail | `#F06A6A` | Failed checks, false alarms (always with ✗ and text) |
| truth | `#8FB8FF` | The true model line on Results (dashed) |

Square corners (2px max), 1px borders, no shadows, no gradients, no pill shapes.

## Layout (every workspace)
CSS grid, top to bottom:
1. **Menu bar** (28px): EXOPLANET-LAB wordmark in accent; File, Scenario, Pipeline, View, Help; current file name on the right.
2. **Workspace tabs** (34px): Scenario · Data · Pipeline · Results · Scoring. Active tab has a 2px accent top line. Blind-mode indicator and the orange Run button on the right.
3. **Main area**: left panel (260px) · viewport (flexible) · Inspector (300px, full height down to the status bar).
4. **Bottom panel** (190px) under the left panel and viewport: tabbed (Console, Timeline, Comparison, Results table…).
5. **Status bar** (24px): seed, preset, blind state, point count, cursor readout.

Panels have a 26px header with uppercase tabs; the active tab has an accent underline. The viewport has a vertical tool strip (select, zoom, pan, measure, fit to view).

## Workspaces
| Workspace | Left panel | Viewport | Inspector | Bottom |
| --- | --- | --- | --- | --- |
| Scenario | Preset tree + recent runs | Preset range bars | Seed, blind mode, data style, Generate | Console |
| Data | Dataset columns + summary stats | Zoomed light curve, cursor readout | Display, selection, export | Timeline with draggable selection window |
| Pipeline | Node graph: Raw → Detrend → BLS → Fold → Fit → Vet (+ Code tab) | Selected node's chart | Node parameters, Run node, outputs | Console log (+ Problems, History) |
| Results | Run info and settings used | Folded transit + residuals strip | Outcome, vetting checklist, truth, Save | Comparison table (yours vs truth, 1σ/2σ) |
| Scoring | Batch runs list + filters | 4 panes: detection vs SNR, size × noise table, outcomes by preset, real TESS planets | Summary stats, export | Per-scenario results table (+ SQL tab) |

## Components
- **Inspector rows**: label (110px, muted) + control; inputs 24px tall, dark fill, 1px border.
- **Nodes**: header strip with name and status (✓ done / ● selected / ○ queued), body with method and key output; selected node has an accent border; connectors are 1px lines with small ports.
- **Console**: monospace log; commands in text color, successes in pass green, warnings in accent.
- **Tables**: spreadsheet style, 24px rows, 1px grid lines.

## Charts (Plotly in Phase 5)
- Dark plot area (`#141414`), grid lines `#262626`, axis frame `#3A3A3A`, tick labels in muted mono 11px.
- Data points light gray/white; binned points brighter than raw.
- Model fits in accent; truth dashed in `#8FB8FF`; alias markers dashed gray.
- Axis labels in lowercase with units in brackets, e.g. `time [d]`, `flux [norm]`.

## Optional extras (owner may cut later)
- Code tab in the node graph, SQL tab and "Open in DuckDB console" on Scoring, residuals strip on Results.

## Implementation notes for Phase 5
- Resizable docked panels may need one small React layout library; ask before adding it.
