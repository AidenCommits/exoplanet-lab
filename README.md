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

### Requirements files
- `pyproject.toml`: the Python packages the project uses.
- `uv.lock`: the exact pinned versions (used by `uv sync`).
- `requirements.txt`: the same pinned list for plain pip
  (`pip install -r requirements.txt`).
- `.python-version`: the Python version.
- Frontend packages will live in `frontend/package.json` once the frontend exists.
