---
status: accepted
---

# The flake is the only way claws is delivered

Claude Code has a plugin marketplace and Codex has its own plugin layer. claws uses neither. Both are specific to one harness, and the whole point here is a single set of baps that works in every harness Shane runs. The flake exposes four things: the claws package, a `lib.project` function for declaring baps in a repo's own flake, a home-manager module for global installs, and an `install` app for writing project-level config into a repo ad hoc. Consumers either take claws as a flake input or run the installer with `nix run`. There is no npx path, no curl-to-bash, and no vendored copy of the baps in a consuming repo.

## Considered options

- Ship as a Claude plugin and a Codex plugin side by side. Rejected because the two formats would drift and neither covers a third harness.
- A standalone installer that works without Nix. Rejected because it would have to solve the runtime question (ADR 0001) all over again.

## Consequences

- A repo that wants claws hooks needs Nix available on the machine running the agent. That is already true everywhere Shane works.
- Project-level hook config written by the installer points at Nix store paths, so it is machine-specific. The installer writes it to `.claude/settings.local.json` and `.codex/hooks.json` and adds both to `.git/info/exclude`. What gets committed is the declaration: either `claws.lib.project` in the repo's flake, whose dev shell re-syncs the files, or a `.claws.json` manifest written by the ad hoc installer.
