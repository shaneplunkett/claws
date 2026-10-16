#!/bin/sh
# Fails if any file silences a checker. Agents reach for these under
# pressure, so the ban is mechanical. --untracked scans new files too, and
# still skips anything gitignored.
set -u

pattern='deadnix: *skip|noqa|type: *ignore|pyright: *ignore|fmt: *(off|skip)'

if git grep --untracked -n -E "$pattern" -- '*.nix' '*.py' '*.pyi'; then
  echo
  echo "Suppression comments aren't allowed. Fix the finding instead."
  echo "If a rule is wrong for this case, change its config in the open and say why."
  exit 1
fi
