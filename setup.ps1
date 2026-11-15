<#
.SYNOPSIS
    One-time setup for exoplanet-lab on a Windows computer.

.DESCRIPTION
    Run from the repo folder:
        powershell -ExecutionPolicy Bypass -File .\setup.ps1

    1. Installs Git, uv, Node.js (LTS) and Claude Code if they are missing.
    2. Installs the newest Python that every package supports
       (tries 3.15 first, then older versions) and creates the .venv environment from pyproject.toml / uv.lock.
    3. Writes requirements.txt (pinned list for plain pip).
    4. First time only: creates the git repo, makes the first commit and pushes to GitHub.

    It is safe to run again; steps that are already done are skipped.
#>

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$RepoUrl = "https://github.com/__GITHUB_USER__/exoplanet-lab.git"
$PythonCandidates = @("3.15", "3.14", "3.13", "3.12")

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Update-SessionPath {
    # Pick up PATH changes made by installers without reopening the terminal.
    $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machine;$user;$env:USERPROFILE\.local\bin"
}

function Test-Command([string]$Name) {
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Install-WithWinget([string]$Command, [string]$WingetId, [string]$Label) {
    if (Test-Command $Command) {
        Write-Host "$Label is already installed."
        return
    }
    Write-Host "Installing $Label..."
    winget install --id $WingetId -e --source winget --accept-package-agreements --accept-source-agreements
    Update-SessionPath
    if (-not (Test-Command $Command)) {
        throw "$Label was installed but '$Command' isn't on PATH yet. Close this window, open a new PowerShell and run setup.ps1 again."
    }
}

# --- 1. Tools ---------------------------------------------------------------
Write-Step "Checking tools (Git, uv, Node.js, Claude Code)"
Update-SessionPath
Install-WithWinget -Command "git" -WingetId "Git.Git" -Label "Git"
Install-WithWinget -Command "uv" -WingetId "astral-sh.uv" -Label "uv"
Install-WithWinget -Command "node" -WingetId "OpenJS.NodeJS.LTS" -Label "Node.js LTS"

if (Test-Command "claude") {
    Write-Host "Claude Code is already installed."
} else {
    Write-Host "Installing Claude Code (official installer)..."
    Invoke-RestMethod https://claude.ai/install.ps1 | Invoke-Expression
    Update-SessionPath
}

# --- 2. Python environment ----------------------------------------------------
Write-Step "Setting up the Python environment"
$chosen = $null
if (Test-Path ".python-version") {
    $chosen = (Get-Content ".python-version" -Raw).Trim()
    Write-Host "Using pinned Python $chosen from .python-version"
    uv python install $chosen
    uv sync
    if ($LASTEXITCODE -ne 0) { throw "uv sync failed." }
} else {
    foreach ($version in $PythonCandidates) {
        Write-Host "Trying Python $version..."
        uv python install $version
        if ($LASTEXITCODE -ne 0) { continue }
        uv sync --python $version
        if ($LASTEXITCODE -eq 0) {
            $chosen = $version
            uv python pin $version
            break
        }
        Write-Host "Some packages don't support Python $version yet; trying an older version." -ForegroundColor Yellow
        if (Test-Path ".venv") { Remove-Item ".venv" -Recurse -Force }
        if (Test-Path "uv.lock") { Remove-Item "uv.lock" -Force }
    }
    if (-not $chosen) { throw "Couldn't build the environment with any of: $($PythonCandidates -join ', ')" }
}
Write-Host "Python environment ready (Python $chosen)." -ForegroundColor Green

Write-Step "Writing requirements.txt"
uv export --format requirements-txt --no-hashes --all-groups -o requirements.txt
if ($LASTEXITCODE -ne 0) { throw "uv export failed." }

# --- 3. Git: first commit and push (first run only) ---------------------------
if (-not (Test-Path ".git")) {
    Write-Step "Creating the git repo and pushing the first commit"
    if (-not (git config --global user.name)) {
        $name = Read-Host "Your name for git commits"
        git config --global user.name $name
    }
    if (-not (git config --global user.email)) {
        $email = Read-Host "Your email for git commits (the one on your GitHub account)"
        git config --global user.email $email
    }
    git init -b main
    git add .
    git commit -m "Project setup: README, CLAUDE.md, Python environment and setup script" `
        -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" `
        -m "Claude-Session: https://claude.ai/code/session_01HPbUVNV9fTzyVTppXDHbQK"
    git remote add origin $RepoUrl
    Write-Host "Pushing to GitHub. A GitHub sign-in window may open; sign in there." -ForegroundColor Yellow
    git push -u origin main
    if ($LASTEXITCODE -ne 0) { throw "git push failed." }
}

# --- Summary ------------------------------------------------------------------
Write-Step "Done"
Write-Host ("git:    " + (git --version))
Write-Host ("uv:     " + (uv --version))
Write-Host ("node:   " + (node --version))
Write-Host ("python: " + (uv run python --version))
if (Test-Command "claude") { Write-Host ("claude: " + (claude --version)) }
Write-Host ""
Write-Host "Next: run 'claude' in this folder and sign in with your personal account." -ForegroundColor Green
