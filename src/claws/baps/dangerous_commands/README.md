# dangerous-commands

Paws off the dangerous stuff. A PreToolUse guard for shell commands and file edits.

Rules have a level: critical, high, medium or low. `level` is the lowest level that fires, default high. A fired rule denies, unless its level is in `ask`, and levels in `deny` always deny (default critical).

```nix
programs.claws.bap.dangerous-commands = {
  enable = true;
  level = "high";
  ask = true;                       # or [ "high" "medium" ]
  deny = [ "critical" ];
  unattended = "deny";              # what an ask becomes when no prompt can be shown
  disable = [ "git-branch-D" ];
  allow = [ "systemctl restart plex$" ];
  rules = [
    { id = "unraid"; level = "high"; pattern = "\\bunraid\\b"; reason = "leave unraid alone"; }
    { id = "no-pct"; pattern = "pct "; scope = "command"; reason = "containers are Terraform's"; }
    { id = "no-lock"; pattern = "flake\\.lock$"; tools = [ "edit" ]; reason = "the lock is CI's job"; }
  ];
};
```

The same keys go under `baps.dangerous-commands` in a project `.claws.json`.

## ask needs a human

`ask` only means something when the harness will show a prompt. Claude Code in `--dangerously-skip-permissions` mode auto-approved a hook `ask` with no prompt, and `-p` runs deny it outright. The payload carries `permission_mode`, so when it is `bypassPermissions` or `dontAsk` the bap applies `unattended` instead: `deny` (the default) refuses and says why, `allow` lets it through, `ask` trusts the harness anyway.

## What it will not catch

The target is ordinary accidental command generation, not a sandbox. A static rule cannot see through these, and the test suite pins them as known limits so the list stays honest:

- A target behind a runtime variable: `target=/; rm -rf "$target"`. `~`, `$HOME` and `${HOME}` are matched because they are fixed spellings.
- Anything done inside an interpreter: `python3 -c 'shutil.rmtree(...)'`, Perl, Node.
- A script or Makefile target in the repo: `./deploy.sh`, `make nuke`.
- A carrier the parser does not know: `docker exec box rm -rf /`. Known carriers are listed in `core/shell.py`.
- Recursive rm of an ordinary path is `low`, so at the default level `rm -rf node_modules` passes. If accidental data loss is the worry, run `level = "low"` with `ask = true`.

Hook self-protection covers the config files and the `.claude` and `.codex` directories themselves against rm, mv, cp, ln, install, chmod and redirects. It does not cover the same done from Python, or editing a repo flake that re-renders the config on the next dev shell.

## How a command is read

Rules do not run over the raw string. The command line is split into the simple commands it would run (on `;`, `&&`, `||`, `|`, newlines and `$(...)`), heredoc bodies and comments are dropped, tokens are unquoted, and carriers such as `ssh host '...'`, `bash -c '...'`, `sudo`, `timeout`, `xargs` and `nix develop -c` are followed into their inner command. Each rule has a scope:

- `command` (the default): anchored at the command word of each simple command, with `sudo`, `env`, `timeout` and similar allowed in front. `git commit -m "rm -rf /"` does not match; `ssh pve1 'qm stop 105'` does.
- `segment`: anywhere in one simple command's unquoted tokens. Used for redirect targets like `> /dev/sda`.
- `pipeline`: anywhere in a whole pipeline. Used for `curl ... | sh`.
- `raw`: anywhere in the raw text. Used for SQL inside quotes and fork bombs.

Extra `rules` default to `segment`, since hand-written patterns are usually substrings. Set `scope` to change that. A carrier the parser does not know about hides its inner command from `command` rules; see `_carrier_inner` in `core/shell.py`.

Built-in rules are the `BUILTIN` table in `bap.py`. They cover the usual rm, dd and mkfs horrors, force pushes and pushes straight to main, `git reset --hard`, terraform and tofu applies, Proxmox `qm`, `pct` and `pvesh` changes, `nixos-rebuild switch` and friends, `systemctl stop` and `restart`, and edits to any agent hook config. Every rule has a row in `tests/test_dangerous_commands.py`, and a test fails if a rule is added without one.

Denies and asks are logged to `~/.local/state/claws/dangerous-commands.jsonl`. `CLAWS_NO_LOG=1` turns that off.
