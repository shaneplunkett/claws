"""The bap contract and discovery.

A bap is one claws hook: a package under claws.baps that exposes a module-level
BAP. Drop a new directory in and it is found; nothing else has to be edited on
the Python side. The Nix side discovers the same directories via each bap's
bap.nix.
"""

from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Callable
from dataclasses import dataclass

from .events import Decision, Event
from .jsontypes import JsonObject


@dataclass(frozen=True)
class Bap:
    name: str
    event: str  # PreToolUse, PostToolUse, SessionStart, UserPromptSubmit, Stop
    run: Callable[[Event, JsonObject], Decision]
    tools: tuple[str, ...] = ()  # tool classes it wants; empty for non-tool events
    timeout: int = 10  # seconds the harness should allow
    fail_closed: bool = False  # on a crash or bad payload, deny (True) or stay quiet (False)
    defaults: JsonObject | None = None  # default options

    def options(self) -> JsonObject:
        return dict(self.defaults or {})


def discover() -> dict[str, Bap]:
    import claws.baps

    found: dict[str, Bap] = {}
    for info in pkgutil.iter_modules(claws.baps.__path__):
        if not info.ispkg or info.name.startswith("_"):
            continue
        module = importlib.import_module(f"claws.baps.{info.name}")
        bap = getattr(module, "BAP", None)
        if not isinstance(bap, Bap):
            raise TypeError(f"claws.baps.{info.name} must expose BAP: Bap")
        if bap.name != info.name:
            raise ValueError(f"claws.baps.{info.name} declares name {bap.name!r}; they must match")
        found[bap.name] = bap
    return dict(sorted(found.items()))


def names() -> list[str]:
    return list(discover())


def get(name: str) -> Bap:
    baps = discover()
    try:
        return baps[name]
    except KeyError:
        raise ValueError(f"unknown bap {name!r}; known: {list(baps)}") from None
