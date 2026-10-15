# claws

Baps for Claude Code and Codex, shipped as a Nix flake.

A hook is a small program a coding agent runs at a fixed point in its loop: before a shell command, after a file edit, at session start. Claude Code and Codex both support them, with the same event names and almost the same wire format, but different config files and slightly different payloads. A bap is one claws hook. claws keeps one copy of each bap and lets the flake handle the per-harness differences.

## What you get

- A Python package, `claws`, with one entrypoint for every bap. Stdlib only, no third-party deps.
- A Nix function that turns a chosen set of baps into the hooks block each harness wants.
- A home-manager module for installing baps globally.
- A `lib.project` function for declaring baps in a repo's own flake.
- An installer, `nix run .#install`, for the ad hoc case.
- Tests for every bap under `nix flake check`, using payloads captured from both harnesses.

## Layout

```
flake.nix                outputs: packages, lib, homeManagerModules, apps.install, checks, devShells
nix/                     lib.nix renders a hook set into harness config; hm-module.nix; hooks.nix discovers hook.nix files
src/claws/
  core/                  events, JSON types, config layering, the bap registry
  adapters/              one module per harness: payload in, response out
  cli/                   claws-bap, claws-install, claws-manifest
  baps/<name>/           one package per bap: bap.py, bap.nix, README.md, tests/
  fixtures/<harness>/    real payloads captured from each harness, one file per event
  testing.py             builders and runners shared by every test
tests/                   cross-cutting: adapters, config, cli, install, manifest, registry
docs/adr/                why things are the way they are
docs/adding-a-bap.md     the checklist for a new bap
```

## Using it

As a flake input in home-manager:

```nix
inputs.claws.url = "git+ssh://forgejo@forge/shane/claws";

# in home config
imports = [ inputs.claws.homeManagerModules.default ];
programs.claws = {
  enable = true;
  harnesses = [ "claude" "codex" ];
  bap.paws = { enable = true; level = "high"; ask = true; };
};
```

In a repo's own flake, declaratively:

```nix
let
  clawsCfg = inputs.claws.lib.project {
    inherit pkgs;
    harnesses = [ "claude" "codex" ];
    bap.paws = { level = "high"; ask = true; };
  };
in {
  devShells.default = pkgs.mkShell { shellHook = clawsCfg.shellHook; };
  apps.claws = clawsCfg.app;   # nix run .#claws syncs by hand
}
```

Entering the dev shell syncs `.claude/settings.local.json` and `.codex/hooks.json` to match the flake. Both contain Nix store paths, so they are per machine; the installer adds them to `.git/info/exclude`.

Ad hoc, without a flake:

```sh
nix run github:shaneplunkett/claws#install -- --harness claude,codex --baps paws --set paws.ask=true
```

That writes a committable `.claws.json` with the chosen baps and options, then the same two harness files pointing at it.

## Baps

Each bap has its own README next to its code.

- [paws](src/claws/baps/paws/README.md): PreToolUse guard for dangerous shell commands and edits to hook config.

## How config is found

Lowest to highest: the bap's defaults, then `--config FILE` (or `$CLAWS_CONFIG`), which is what the home-manager module passes, then `.claws.json` in the working directory or any parent up to the git root. Scalars override, lists concatenate, so a repo can add rules and allows on top of your global ones. A repo can also lower `level`, which is why paws refuses edits to `.claws.json` and the harness settings files.

## Failure policy

A bap always exits 0 and speaks through its JSON. If it crashes or gets a payload it cannot parse, a bap with `fail_closed=True` (paws) denies with the error in the reason; others stay quiet. Either way the error goes to stderr and the log.

## Codex notes

Codex only runs project-level hooks it trusts. Either trust them once interactively, or pass `--dangerously-bypass-hook-trust` to `codex exec`. Codex 0.162 sends Claude-shaped payloads for shell commands; edits arrive as `apply_patch` and the adapter pulls the file paths out of the patch header.

## Status

One bap, end to end. `nix flake check` runs the Python tests, strict mypy, ruff, nixfmt, statix and deadnix, a check that the Nix renderer matches the Python one, an eval of the home-manager module, and a run of the project installer inside a fresh git repo. The deny path has been run live against both harnesses, and claws installs paws into its own repo from its dev shell.
