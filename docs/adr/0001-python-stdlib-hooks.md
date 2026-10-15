---
status: accepted
---

# Baps are Python, stdlib only, with Nix as the only runtime provider

The inspiration repo (karanb192/claude-code-hooks) writes hooks in JavaScript and relies on npx to run them. claws is delivered by a Nix flake, so the flake pins the interpreter and nothing needs to be installed by the user. That removes the "ship uv or bun" question entirely. Given that, Python wins on three points: no build step, `python3 -I` so a planted module in the target repo cannot be imported by a hook, and a stdlib (json, re, subprocess, pathlib) that covers everything a hook does. Startup cost is about 25 ms per hook run, which is fine for something that fires per tool call.

## Considered options

- JavaScript on Node or Bun. Easier porting from the inspiration repo, and Bun starts faster. Rejected because every hook would need a package.json and a lockfile for Nix to build, and there is no equivalent of `-I` for import isolation.
- Bash plus jq, which is what the caboodle hooks use today. Fine for four hooks, painful to test and to share code across twenty.

## Consequences

- Third-party Python packages are not allowed in baps. If one ever seems necessary, that is a signal the bap is doing too much.
- Tests use pytest from the dev shell, which is the one place a non-stdlib dependency is fine.
