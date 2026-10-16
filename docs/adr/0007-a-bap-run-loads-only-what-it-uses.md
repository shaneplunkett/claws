---
status: accepted
---

# A bap run loads only its adapter, its own bap and the stdlib it uses

Baps should be cheap enough to run on every tool call without anyone noticing, and claws' own cost mustn't grow as baps are added. On 2026-10-16 a dangerous-commands run cost about 46ms above bare `python3 -I`, and most of that was claws rather than the bap: argparse, dataclasses pulling in `inspect`, a bash wrapper, and registry discovery importing every bap on every call. A throwaway prototype of a lean path, with argv parsed by hand, only the named adapter and bap imported, plain classes instead of dataclasses, and the Nix Python run directly, brought it to about 14ms, with a do-nothing bap at about 4.5ms. So the path from the harness starting a bap to the decision being printed stays lean on purpose. Discovery, the manifest, the installer and the tests can use whatever stdlib they like. Numbers and sources are in `docs/research/2026-10-16-hook-execution-and-overhead.md`.

## Considered options

- One process per event that runs every bap for that event. Rejected: Claude Code and Codex both run matching hooks side by side, so a process per bap already costs about the same waiting time as one. A shared process would also make one bap's crash or timeout every bap's.
- A long-lived daemon with a thin client. The fastest on paper (one project reports 0.3ms per call), but it's a background service to keep alive, it goes stale after every Nix rebuild, and Codex would need its hooks re-trusted each time.
- Charge claws' shared startup to a separate budget. Rejected: that would make the slowdown official instead of fixing it. A bap's budget counts everything above bare Python.

## Consequences

- On the hot path, no `argparse`, `dataclasses`, `inspect`, runtime `typing`, `pathlib` or discovery. `Event`, `Decision` and `Bap` are plain classes. A test checks which modules a real run loaded, so leanness is pinned without timing anything.
- Hand-parsed argv and plain classes look like something to tidy up. Don't tidy them: the bench (SHA-211) fails every bap at once if the hot path gets heavier.
- Python 3.15's `lazy import` would do some of this for us. It's a safety net for later, not a replacement, because what's left on the path is used on every call.
