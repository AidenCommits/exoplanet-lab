# exoplanet-lab: instructions for Claude

## Project goal
A resume-quality data analysis app. It generates astronomical scenarios (v1: exoplanet
transit light curves), runs the owner's analysis pipeline on them, scores the results
and shows them as charts. The full plan is in `Astronomy Data App — Project Plan.docx`.

## Who writes what
- The owner writes the analysis pipeline (detrending, BLS search, phase folding, transit
  fitting, vetting). Claude teaches, explains, reviews and gives hints, but does not
  write that code unless explicitly asked.
- Claude builds everything around the science: the data generator, the API, the frontend,
  the tests and the tooling.

## Working rules
- **Explain first.** Describe the plan before writing code, and wait for approval on
  anything bigger than a small fix.
- **Small commits.** One feature per session, small changes, and a commit after every
  working step.
- Explain astronomy and statistics concepts in plain language first, then in technical detail.
- If a request conflicts with the plan or the tech stack, say so before doing it.

## Tech stack (don't add other languages or frameworks without asking)
| Part | Language | Tools |
| --- | --- | --- |
| Data generator | Python | numpy, scipy, batman |
| Analysis pipeline | Python | astropy (BLS), scipy, lightkurve; numba only if profiling shows a slow loop |
| Notebooks | Python | Jupyter, matplotlib |
| API | Python | FastAPI, Pydantic |
| Frontend | TypeScript | React, Vite, Plotly.js, Tailwind |
| Batch scoring results | Python + SQL | joblib; Parquet files queried with DuckDB |
| Testing | Python / TS | pytest; Vitest, Playwright |
| Tooling | — | uv, ruff, mypy |
| Deployment | — | Frontend on Netlify; API as a container on a Python host |

- Python version: the one pinned in `.python-version` (the newest version that all packages support; setup.ps1 picks it).
- Dependencies live in `pyproject.toml` (exact versions in `uv.lock`). Add packages with
  `uv add <package>`, never with a bare `pip install`, then regenerate `requirements.txt`
  with `uv export --format requirements-txt --no-hashes -o requirements.txt`.
- No database or user accounts in v1.
- Where the Python environment lives depends on where the repo is (decision 13):
  - **Repo outside OneDrive:** uv's default in-repo `.venv` is fine (it is gitignored).
  - **Repo inside OneDrive:** OneDrive locks files inside `.venv`, so the environment lives at
    `%USERPROFILE%\.venvs\exoplanet-lab`, set by the user-level `UV_PROJECT_ENVIRONMENT`
    variable. `setup.ps1` sets this up automatically. Never create a `.venv` inside a OneDrive
    copy of the repo.

  See README.md, "Python environment location".

## Quality bar
Code a hiring manager would respect: clear names, type hints, docstrings, tests for the
generator and the pipeline, and a polished, consistent UI. Use fixed random seeds so every
scenario can be reproduced.

## Common commands
- `uv sync`: install or update the Python environment
- `uv run pytest`: run tests
- `uv run ruff check .` and `uv run ruff format .`: lint and format
- `uv run mypy .`: type-check
- `uv run jupyter lab`: open notebooks
