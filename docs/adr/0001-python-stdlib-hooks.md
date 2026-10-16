---
status: accepted
---

# Baps are Python, stdlib only, with Nix as the only runtime provider

The inspiration repo (karanb192/claude-code-hooks) writes hooks in JavaScript and relies on npx to run them. claws is delivered by a Nix flake, so the flake pins the interpreter and nothing needs to be installed by the user. That removes the "ship uv or bun" question entirely. Given that, Python wins on three points: no build step, `python3 -I` so a planted module in the target repo cannot be imported by a hook, and a stdlib (json, re, subprocess, pathlib) that covers everything a hook does. Interpreter startup is about 11 ms per bap run (measured 2026-10-16), which is fine for something that fires per tool call. Anything above that is the bap's own cost, and each bap declares a budget for it.

## Considered options

- JavaScript on Node or Bun. Easier porting from the inspiration repo, and Bun starts faster. Rejected because every hook would need a package.json and a lockfile for Nix to build, and there is no equivalent of `-I` for import isolation.
- Bash plus jq, which is what the caboodle hooks use today. Fine for four hooks, painful to test and to share code across twenty.

## Consequences

- Third-party Python packages are not allowed in baps. If one ever seems necessary, that is a signal the bap is doing too much.
- Tests and type checks use pytest and mypy as uv dev dependencies, the one place a non-stdlib dependency is fine.
- uv stays out of a bap's run path. `uv run` starts a normal CPython after checking the environment, which doubled startup to 21 ms when measured, so wiring always calls the Nix store's Python directly.
