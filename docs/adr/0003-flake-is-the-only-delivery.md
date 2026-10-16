---
status: accepted
---

# The flake is the only way claws is delivered

Claude Code has a plugin marketplace and Codex has its own plugin layer. claws uses neither. Both are specific to one harness, and the whole point here is a single set of baps that works in every harness Shane runs. The flake exposes three things: the claws package, a `lib.project` function for declaring a repo-scope bap set in that repo's flake, and a home-manager module for the global scope. `flake.nix` declares what is on and `flake.lock` pins which claws it is, so nothing else needs to record it. There is no npx path, no curl-to-bash, no ad hoc installer, and no vendored copy of the baps in a consuming repo.

## Considered options

- Ship as a Claude plugin and a Codex plugin side by side. Rejected because the two formats would drift and neither covers a third harness.
- A standalone installer that works without Nix. Rejected because it would have to solve the runtime question (ADR 0001) all over again.
- An ad hoc `nix run .#install` that wrote a committable `.claws.json` manifest into a repo. The first cut had one, copying what npx-delivered skill tools do (Vercel's `skills-lock.json`, for one). Research on 2026-10-16 (`docs/research/2026-10-16-per-repo-manifests.md`) found those manifests exist because npx has nowhere else to remember what it installed, and a flake already does that job. The manifest was also a side door for per-repo rules, which ADR 0005 rules out. Removed.

## Consequences

- A repo that wants claws needs Nix available on the machine running the agent. That is already true everywhere Shane works.
- A repo with no flake, or one Shane can't change, gets only the global scope.
- Wiring points at Nix store paths, so it is machine-specific. The dev shell's installer writes `.claude/settings.local.json` and `.codex/hooks.json` and adds both to `.git/info/exclude`. What gets committed is the declaration in the repo's flake, and the dev shell re-syncs the wiring from it.
