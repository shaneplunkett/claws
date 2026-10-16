---
status: accepted
---

# Scopes run independently and never merge

A bap can be on globally, from home-manager, and in a repo, from that repo's flake. The first plan was to run it once with the repo's options layered over the global ones: the global run would step aside when the repo declared the same bap, and the repo run would read the global options underneath its own. That needs a per-repo record the global run checks on every call, a stable path for the global options, and merge rules for every option, all for a case that's rare in practice. So the scopes don't merge. Each runs its own bap set with its own options, and a bap on in both runs twice. That's the user's call, and so is the cost. The reasoning is also in `.out-of-scope/merging-scopes.md`.

## Considered options

- Global stands down and the repo layers over it. Rejected for the machinery above. It would also have needed its own rule to stop a repo loosening what global set.
- The repo's wiring leaves out baps that are already on globally. Rejected: a missed dev shell re-sync after a global change could leave a guard running zero times.
- Make the global and repo commands identical so the harness dedupes them. Rejected: Codex 0.162.1 runs identical commands twice anyway, and Claude Code doesn't define what counts as the same handler.

## Consequences

- A repo can't loosen or switch off what global turned on, because the global run always happens with the global options. A repo can only add on top, such as caboodle turning on dangerous-commands' tofu and proxmox groups.
- Any deny from either run wins, on both harnesses.
- A doubled bap costs CPU more than waiting time, because both harnesses run matching hooks side by side.
- A bap that changes files, such as a formatter, only makes sense per repo, so nothing guards against wiring one in both scopes.
