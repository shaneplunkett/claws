---
status: accepted
---

# A bap always answers before the harness gives up on it

When a hook runs past its timeout, Claude Code and Codex both kill it and carry on as if it said nothing. On PreToolUse, saying nothing means the tool call goes ahead. A bap's `fail_closed` only works when the bap gets to print its answer, so a guard that hangs would let the command through: the one way of failing that the design didn't cover. So every bap runs against its own deadline, set comfortably inside the timeout it declares to the harness. When the deadline passes, the bap answers by its `fail_closed` setting: a guard denies, and anything else passes and gets out of the way. The deadline lives in the shared entry point, so no bap has to implement it. Harness behaviour is in `docs/research/2026-10-16-hook-execution-and-overhead.md`.

## Considered options

- Trust the harness timeout. Rejected: both harnesses fail open on a timeout, which breaks `fail_closed` for guards.
- Claude Code's `onFailure: "block"` alone. Rejected as the only answer, because Codex has no equivalent. It's kept as a backup for guards on Claude Code, for a hang before the deadline starts.

## Consequences

- `fail_closed` now holds whether a bap crashes, gets a bad payload or runs out of time.
- A guard that's merely slow gets a deny, with a reason saying it ran out of time, rather than a silent allow. If that ever fires, the bench (SHA-211) should have caught the slowness first.
- The deadline has to cost next to nothing on the hot path (ADR 0007).
