# exoplanet-lab

Generate realistic exoplanet transit light curves, run an analysis pipeline to find the
planets hidden in them, and score how well the pipeline did.

> Status: early setup. More to come.

## Setting up on a new computer (Windows)

1. Clone the repo:
   ```powershell
   git clone https://github.com/AidenCommits/exoplanet-lab.git
   cd exoplanet-lab
   ```
   (If Git isn't installed yet, install it first with `winget install --id Git.Git -e`.)
2. Run the setup script from the repo folder:
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\setup.ps1
   ```
   It installs Git, uv, Node.js and Claude Code if they're missing, then installs Python
   and every package listed in `pyproject.toml` / `uv.lock`.

### Python environment location
OneDrive locks files while it syncs them, which makes `uv sync` fail with "Access is denied"
when the environment is inside a OneDrive folder. So on this machine the environment lives
**outside the repo**, set by a Windows user environment variable:

| Setting | Value |
| --- | --- |
| Variable | `UV_PROJECT_ENVIRONMENT` (user-level) |
| Environment folder | `%USERPROFILE%\.venvs\exoplanet-lab` |
| Set on | 2026-11-16 (also logged in `docs/decisions.md`) |

- `uv sync`, `uv run` and the other `uv` commands read this variable automatically. There is
  no `.venv` folder in the repo.
- `setup.ps1` sets the variable for you when the repo is inside OneDrive.
- The variable applies to **every uv project** on this Windows account. If you start another uv
  project, override it in that terminal (`$env:UV_PROJECT_ENVIRONMENT = ".venv"`) or remove it.
- Terminals (and Claude Code) opened before the variable was set don't see it; reopen them.
- To check it: `[Environment]::GetEnvironmentVariable("UV_PROJECT_ENVIRONMENT", "User")`.
- To undo: `[Environment]::SetEnvironmentVariable("UV_PROJECT_ENVIRONMENT", $null, "User")`,
  delete `%USERPROFILE%\.venvs\exoplanet-lab`, reopen the terminal and run `uv sync`.
- If `uv sync` reports "failed to hardlink ... (os error 396)", run `uv sync --link-mode=copy`
  once. It happens when uv's cache is still linked to files inside OneDrive.

### Requirements files
- `pyproject.toml`: the Python packages the project uses.
- `uv.lock`: the exact pinned versions (used by `uv sync`).
- `requirements.txt`: the same pinned list for plain pip
  (`pip install -r requirements.txt`).
- `.python-version`: the Python version.
- Frontend packages will live in `frontend/package.json` once the frontend exists.
