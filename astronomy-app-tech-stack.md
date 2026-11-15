# Astronomy Data App — Tech stack (follow this when writing code)

Full plan: https://claude.ai/artifact/SfrXveDFvyHViMbSyUHFuZ

Rule: Python for the science and the API; TypeScript for the frontend. No other languages unless this file is updated.

| Part | Language | Tools |
| --- | --- | --- |
| Data generator | Python 3.12 | numpy, scipy, batman |
| Analysis pipeline | Python 3.12 | astropy (BLS), scipy, lightkurve; numba only if profiling shows a slow loop |
| Notebooks | Python | Jupyter, matplotlib |
| API | Python | FastAPI, Pydantic |
| Frontend | TypeScript | React, Vite, Plotly.js, Tailwind |
| Batch scoring results | Python + SQL | joblib; Parquet files queried with DuckDB |
| Testing | Python / TS | pytest; Vitest, Playwright |
| Tooling | — | uv, ruff, mypy |
| Deployment | — | Frontend on Netlify; API as a container on a Python host |

Working rules:
- The user writes the analysis pipeline (Phase 4) themselves; Claude tutors and reviews but does not write that code.
- One feature per session: plan first, get approval, then build. Commit after each working step.
- No database or user accounts in v1.
