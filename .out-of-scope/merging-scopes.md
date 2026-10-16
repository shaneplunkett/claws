# Merging scopes

claws doesn't merge a bap's global and repo scopes. If a bap is on in both, it runs twice: once with the global options and once with the repo's. Neither run knows about the other.

## Why this is out of scope

The first plan was "run once, repo layered over global". The global run would step aside when the repo declared the same bap, and the repo run would read the global options underneath its own. That needs a per-repo record the global run checks on every call, a stable path for the global options, and merge rules for every option. That's a lot of machinery for what turned out to be a rare case. Running both is simpler and gets everything we wanted:

- **A repo can't loosen global.** The global run always happens, with the global options, so a repo can only add on top. "The floor can't be switched off from any scope" holds with no merge code.
- **Correctness holds.** On both Claude Code and Codex, any deny from a matching hook wins.
- **The cost is small.** Both harnesses run matching hooks side by side, so a doubled bap mostly costs CPU, not waiting time.

The harnesses won't dedupe for us anyway. Codex (0.162.1) appends every config layer and runs identical commands twice. Claude Code runs "the same handler" only once, but it never defines what counts as the same, and the global and repo commands differ anyway. Details are in `docs/research/2026-10-16-hook-execution-and-overhead.md`.

Turning a bap on in both scopes is the user's call, and so is paying for it. In practice it's for guards: dangerous-commands is on globally, and caboodle turns on extra groups in its own flake. A bap that changes files, such as a formatter, only makes sense per repo, because it needs that repo's tools. So there's no guard against wiring one twice either.

## Prior requests

- SHA-212: "Run a bap once when it's on in both scopes, repo layered over global"
