"""claws-install: write a repo's wiring from the bap set its flake declares.

  claws-install --from /nix/store/...-claws.json [--dir .] [--bin PATH] [--quiet]

lib.project's dev shell hook and app run this; there is no ad hoc mode
(ADR 0003). The file names the harnesses and baps, and every bap is pointed
at it as its --config.

The hook entries are merged into .claude/settings.local.json and
.codex/hooks.json. Those contain Nix store paths, so they are per machine;
the installer adds them to .git/info/exclude. Existing entries are kept;
entries that point at an older claws build are replaced.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from ..core import registry
from ..core.jsontypes import HookBlock, HookEntry, Json, JsonObject, as_object, as_str_list, loads
from .manifest import render

TARGETS = {
    "claude": Path(".claude") / "settings.local.json",
    "codex": Path(".codex") / "hooks.json",
}


def bin_path() -> str:
    env = os.environ.get("CLAWS_BIN")
    if env:
        return env
    sibling = Path(sys.argv[0]).resolve().parent / "claws-bap"
    return str(sibling) if sibling.exists() else "claws-bap"


def is_ours(entry: Json, binary: str) -> bool:
    """An entry we wrote earlier: the same binary, any claws-bap build, or a pre-rename
    claws-hook build."""
    if not isinstance(entry, dict):
        return False
    hooks = entry.get("hooks")
    if not isinstance(hooks, list):
        return False

    def mine(h: Json) -> bool:
        command = str(h.get("command", "")) if isinstance(h, dict) else ""
        return "claws-bap" in command or "claws-hook" in command or command.startswith(binary + " ")

    return any(mine(h) for h in hooks)


def entry_json(entry: HookEntry) -> JsonObject:
    """A TypedDict is a plain dict at runtime; spell it out so the Json type knows too."""
    out: JsonObject = {
        "hooks": [
            {"type": h["type"], "command": h["command"], "timeout": h["timeout"]}
            for h in entry["hooks"]
        ]
    }
    if "matcher" in entry:
        out["matcher"] = entry["matcher"]
    return out


def merge_hooks(existing: JsonObject, rendered: HookBlock, binary: str) -> JsonObject:
    hooks = as_object(existing.get("hooks", {}), "hooks")
    for event, entries in rendered.items():
        current = hooks.get(event, [])
        kept = [e for e in current if not is_ours(e, binary)] if isinstance(current, list) else []
        hooks[event] = [*kept, *(entry_json(e) for e in entries)]
    return {**existing, "hooks": hooks}


def dump(data: JsonObject) -> str:
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def write_json(path: Path, data: JsonObject) -> bool:
    """Write if changed. Returns whether anything was written."""
    text = dump(data)
    if path.exists() and path.read_text() == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return True


def read_json(path: Path, fallback: JsonObject) -> JsonObject:
    return as_object(loads(path.read_text()), str(path)) if path.exists() else fallback


def git_exclude(root: Path, rel: Path) -> None:
    """Keep machine-specific files out of git without touching the repo's .gitignore."""
    info = root / ".git" / "info"
    if not (root / ".git").is_dir():
        return
    exclude = info / "exclude"
    line = rel.as_posix()
    text = exclude.read_text() if exclude.exists() else ""
    if line in text.splitlines():
        return
    info.mkdir(parents=True, exist_ok=True)
    with exclude.open("a") as fh:
        fh.write(("" if not text or text.endswith("\n") else "\n") + line + "\n")


def say(quiet: bool, message: str) -> None:
    if not quiet:
        print(message)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="claws-install")
    parser.add_argument(
        "--from",
        dest="from_file",
        required=True,
        metavar="FILE",
        help="the bap set lib.project generated; baps are pointed at it",
    )
    parser.add_argument("--dir", default=".")
    parser.add_argument("--bin", default=None)
    parser.add_argument("--quiet", action="store_true", help="only speak when something changed")
    args = parser.parse_args(argv)

    root = Path(args.dir).resolve()
    config_path = Path(args.from_file).resolve()
    declared = read_json(config_path, {})
    baps = list(as_object(declared.get("baps", {}), f"{config_path}: baps"))
    declared_harnesses = declared.get("harnesses")
    harnesses = (
        as_str_list(declared_harnesses, f"{config_path}: harnesses")
        if declared_harnesses is not None
        else ["claude", "codex"]
    )

    for name in baps:
        registry.get(name)  # validates
    binary = args.bin or bin_path()
    changed = False
    for harness in harnesses:
        target = root / TARGETS[harness]
        rendered = render(harness, baps, binary, str(config_path))
        if write_json(target, merge_hooks(read_json(target, {}), rendered, binary)):
            changed = True
            say(False, f"{harness}: wrote {target.relative_to(root)}")
        git_exclude(root, TARGETS[harness])
    if not changed:
        say(args.quiet, "claws: baps already up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
