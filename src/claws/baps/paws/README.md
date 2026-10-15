# paws

Paws off the dangerous stuff. A PreToolUse guard for shell commands and file edits.

Rules have a level: critical, high, medium or low. `level` is the lowest level that fires, default high. A fired rule denies, unless its level is in `ask`, and levels in `deny` always deny (default critical).

```nix
programs.claws.bap.paws = {
  enable = true;
  level = "high";
  ask = true;                       # or [ "high" "medium" ]
  deny = [ "critical" ];
  disable = [ "git-branch-D" ];
  allow = [ "systemctl restart plex$" ];
  rules = [
    { id = "unraid"; level = "high"; pattern = "\\bunraid\\b"; reason = "leave unraid alone"; }
    { id = "no-lock"; pattern = "flake\\.lock$"; tools = [ "edit" ]; reason = "the lock is CI's job"; }
  ];
};
```

The same keys go under `baps.paws` in a project `.claws.json`.

Built-in rules are the `BUILTIN` table in `bap.py`. They cover the usual rm, dd and mkfs horrors, force pushes and pushes straight to main, `git reset --hard`, terraform and tofu applies, Proxmox `qm`, `pct` and `pvesh` changes, `nixos-rebuild switch` and friends, `systemctl stop` and `restart`, and edits to any agent hook config. Every rule has a row in `tests/test_paws.py`, and a test fails if a rule is added without one.

Denies and asks are logged to `~/.local/state/claws/paws.jsonl`. `CLAWS_NO_LOG=1` turns that off.
