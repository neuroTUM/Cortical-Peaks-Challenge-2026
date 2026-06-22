set windows-shell := ["powershell", "-NoProfile", "-Command"]

RM_R := if os_family() == "windows" { "Remove-Item -Recurse" } else { "rm -r" }
ON_ERROR_CONTINUE := if os_family() == "windows" { '; $ErrorActionPreference = "Continue"' } else { "|| true" }
RM_PYCACHE := if os_family() == "windows" { 'Get-ChildItem -Path . -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force' } else { 'find . -depth -type d -name "__pycache__" -exec rm -r {} +' }
RM_DS_STORE := if os_family() == "windows" { '' } else { 'find . -depth -type f -name ".DS_Store" -exec rm {} +' }

# module entry points

WHEELCHAIR_MODULE := "games.wheelchair"

# misc constants

DEFAULT_VENV_NAME := ".venv"

_default:
    @ just --choose --quiet || :

alias default := _default

# ====== GAMES ======

[doc('Runs the arcade, forwarding extra flags: just run server | just run server --debug --audit')]
run target *args:
    uv run python -m launcher --target {{ target }} {{ args }}

[doc('Runs the wheelchair game')]
wheelchair:
    uv run python -m {{ WHEELCHAIR_MODULE }}

[doc('Runs the wheelchair game with debug flag')]
wheelchair-debug:
    uv run python -m {{ WHEELCHAIR_MODULE }} --debug

# ====== EXAMPLES ======

[doc('Runs the reference BCI client example')]
example-bci:
    uv run python -m examples.bci_client

# ====== GENERAL/MISC ======

[doc('Installs the dependencies needed for the project')]
install:
    uv sync --dev

[doc('Setup the development environment')]
setup: install
    uv run prek install

[doc('Creates a virtual environment with the provided name else .venv')]
venv name=DEFAULT_VENV_NAME:
    uv venv {{ name }}

[doc('Formats the codebase')]
format:
    uv run ruff format

[doc('Lints the codebase')]
lint:
    uv run ruff check --fix --output-format full

[doc('Type checks the codebase')]
typecheck:
    uv run ty check --output-format full

[unix]
[doc('Runs the test suite')]
test:
    SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy uv run pytest tests/ -v

[windows]
[doc('Runs the test suite')]
test:
    $env:SDL_VIDEODRIVER='dummy'; $env:SDL_AUDIODRIVER='dummy'; uv run pytest tests/ -v

[doc('Runs format, lint and typecheck')]
check: format lint typecheck test

[doc('Cleans the project')]
clean:
    {{ RM_R }} .ruff_cache 			{{ ON_ERROR_CONTINUE }}
    {{ RM_R }} .pytest_cache 		{{ ON_ERROR_CONTINUE }}
    {{ RM_R }} .coverage 			{{ ON_ERROR_CONTINUE }}
    {{ RM_R }} htmlcov 				{{ ON_ERROR_CONTINUE }}
    {{ RM_R }} .venv 				{{ ON_ERROR_CONTINUE }}
    {{ RM_R }} dist					{{ ON_ERROR_CONTINUE }}
    {{ RM_R }} data 				{{ ON_ERROR_CONTINUE }}
    {{ RM_PYCACHE }} 				{{ ON_ERROR_CONTINUE }}
    {{ RM_DS_STORE }} 				{{ ON_ERROR_CONTINUE }}

# ====== DISTRIBUTION ======

[unix]
[doc('Build server + spectator binaries locally (requires Cargo). Usage: just build-dist 0.1.0')]
build-dist version:
    #!/usr/bin/env bash
    set -euo pipefail
    PYTHON_VERSION=$(cat .python-version)
    PYTHON_VERSION_NODOT=${PYTHON_VERSION//./}
    rm -rf dist/
    uv build --wheel --out-dir dist/wheel
    echo "Downloading pygame-ce wheel..."
    uv run --with pip -- python -m pip download "pygame-ce>=2.5.7" \
        --only-binary :all: --no-deps \
        --python-version "$PYTHON_VERSION_NODOT" \
        -d dist/pygame_dl/ --quiet
    echo "Building fat wheel (project + pygame-ce)..."
    WHEEL=$(python3 scripts/fat_wheel.py \
        "$(ls "$PWD"/dist/wheel/cortical_peaks_challenge_2026-*.whl | head -1)" \
        "$(ls dist/pygame_dl/pygame_ce-*.whl | head -1)" \
        "$PWD/dist/")
    echo "Building server binary..."
    PYAPP_PROJECT_NAME=cortical-peaks-challenge-2026 \
    PYAPP_PROJECT_VERSION={{version}} \
    PYAPP_PYTHON_VERSION="$PYTHON_VERSION" \
    PYAPP_EXEC_SPEC=launcher:main_server \
    PYAPP_DISTRIBUTION_EMBED=true \
    PYAPP_PROJECT_PATH="$WHEEL" \
    cargo install pyapp --version 0.29.0 --locked --root dist/server --force
    mv dist/server/bin/pyapp dist/server/bin/cpc-server
    echo "Building spectator binary..."
    PYAPP_PROJECT_NAME=cortical-peaks-challenge-2026 \
    PYAPP_PROJECT_VERSION={{version}} \
    PYAPP_PYTHON_VERSION="$PYTHON_VERSION" \
    PYAPP_EXEC_SPEC=launcher:main_spectator \
    PYAPP_DISTRIBUTION_EMBED=true \
    PYAPP_PROJECT_PATH="$WHEEL" \
    cargo install pyapp --version 0.29.0 --locked --root dist/spectator --force
    mv dist/spectator/bin/pyapp dist/spectator/bin/cpc-spectator
    echo "Done. Binaries at dist/server/bin/cpc-server and dist/spectator/bin/cpc-spectator"
