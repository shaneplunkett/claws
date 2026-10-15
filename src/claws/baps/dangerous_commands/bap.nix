# Mirror of BAP in bap.py. `nix flake check` fails if they drift.
{
  event = "PreToolUse";
  tools = [
    "shell"
    "edit"
  ];
  timeout = 10;
}
