# claws

Baps (agent hooks) for Claude Code and Codex, written once in stdlib Python and delivered through a Nix flake. claws installs its own baps into this repo from the dev shell, so the dangerous-commands guard is live while you work here.

Read `GLOSSARY.md` for the words (bap, harness, adapter, decision) and `docs/adr/` for why things are the way they are. `docs/adding-a-bap.md` is the checklist for a new bap.

## Checks

`scripts/check.sh` is the gate: pre-commit, CI and the agent hooks all run it. Fix what it reports. If a rule is wrong for the case, change its config in the open and say why.

## Tickets

Linear project `claws`, in the Engineering team.
