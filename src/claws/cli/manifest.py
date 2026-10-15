"""Bap manifest and per-harness config rendering.

Nix mirrors this in each bap's bap.nix; `nix flake check` asserts the two agree.
"""

from __future__ import annotations

import argparse
import json
import sys

from .. import adapters
from ..core import registry
from ..core.jsontypes import HookBlock, HookEntry, JsonObject


def manifest() -> JsonObject:
    out: JsonObject = {}
    for name, spec in registry.discover().items():
        out[name] = {"event": spec.event, "tools": list(spec.tools), "timeout": spec.timeout}
    return out


def render(harness: str, baps: list[str], bin_path: str, config_path: str | None = None) -> HookBlock:
    """Return the {event: [entries]} block a harness wants in its hook config."""
    adapter = adapters.get(harness)
    out: HookBlock = {}
    for name in baps:
        spec = registry.get(name)
        command = f"{bin_path} {name} --harness {harness}"
        if config_path:
            command += f" --config {config_path}"
        entry: HookEntry = {"hooks": [{"type": "command", "command": command, "timeout": spec.timeout}]}
        if spec.tools:
            entry["matcher"] = "|".join(adapter.matchers[t] for t in spec.tools)
        out.setdefault(spec.event, []).append(entry)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="claws-manifest")
    parser.add_argument("--render", metavar="HARNESS")
    parser.add_argument("--baps", default=",".join(registry.names()))
    parser.add_argument("--bin", default="claws-bap")
    parser.add_argument("--config", default=None)
    args = parser.parse_args(argv)
    data: JsonObject | HookBlock = (
        render(args.render, args.baps.split(","), args.bin, args.config) if args.render else manifest()
    )
    json.dump(data, sys.stdout, indent=2, sort_keys=True)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
