#!/bin/sh
# The gate: the one check for this repo. Pre-commit, CI and the agents'
# hooks all run exactly this, so there's one answer to "is the repo clean".
set -eu
cd "$(git rev-parse --show-toplevel)"

scripts/check-suppressions.sh

git ls-files --cached --others --exclude-standard -z '*.nix' | xargs -0 -r nixfmt --check
statix check .
deadnix --fail .

ruff format --check .
ruff check .
uv run mypy .
uv run pytest

# The package build with its tests, the Nix-vs-Python manifest sync, and
# evals of lib.project and the home-manager module.
nix --option warn-dirty false flake check
